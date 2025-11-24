from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import math
import time
import uuid
import json
import logging
from pathlib import Path
from collections import defaultdict, deque

# Import moral rules from ethics module (single source of truth)
try:
    from src.ethics import S_morals
except ImportError:
    from ethics import S_morals

# Optional imports for checkpointing (graceful degradation if not available)
try:
    try:
        from src.checkpoint import create_checkpoint
    except ImportError:
        from checkpoint import create_checkpoint
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False
    def create_checkpoint(*args, **kwargs):
        pass
try:
    try:
        from src.shadow_eval import run_shadow_eval
    except ImportError:
        from shadow_eval import run_shadow_eval
except ImportError:
    def run_shadow_eval(*args, **kwargs):
        return None


# ----------  Static Rules (frozen config)  ----------

@dataclass(frozen=True)
class StaticRules:
    allow_self_generated_scenarios_after: float = 0.30   # Comp% threshold
    external_prediction_after: float = 0.05              # minimal Comp%
    max_comp_cap: float = 99.99
    min_comp_floor: float = 0.01
    reevaluation_interval_events: int = 25              # Reval_int (by count)
    checkpoint_interval_events: int = 50                 # Checkpoint every N events
    replay_buffer_size: int = 128
    reward_scale: float = 0.1                            # small continual rewards
    shadow_eval_after_events: int = 100       # how often we *may* call shadow_eval
    max_shadow_eval_runtime_sec: float = 2.0  # soft bound for safety
    disagreement_ratio_warn: float = 0.3      # if disagreements/events > 0.3, flag subject

S_rules = StaticRules()

# ----------  Sources & Skepticism  ----------

@dataclass
class Source:
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    trust: float = 0.5  # 0..1; updated over time
    samples: int = 0

class SourceRegistry:
    def __init__(self):
        self.sources: Dict[str, Source] = {}
    def add(self, name: str, parent_id: Optional[str] = None, base_trust: float = 0.5) -> str:
        s = Source(name=name, parent_id=parent_id, trust=base_trust)
        self.sources[s.id] = s
        return s.id
    def get(self, sid: str) -> Source:
        return self.sources[sid]
    def inherited_trust(self, sid: str) -> float:
        s = self.sources[sid]
        t = s.trust
        hops = 0
        while s.parent_id and s.parent_id in self.sources and hops < 4:
            s = self.sources[s.parent_id]
            t = 0.7 * t + 0.3 * s.trust  # blend with parent trust
            hops += 1
        return t

# ----------  Knowledge Base  ----------

@dataclass
class Claim:
    subject: str
    info: Any
    label: Optional[Any] = None  # ground truth if known
    source_ids: List[str] = field(default_factory=list)
    own: bool = False            # Own_ideas marker
    timestamp: float = field(default_factory=time.time)

class KnowledgeBase:
    def __init__(self):
        self.claims: List[Claim] = []
        self.by_subject: Dict[str, List[int]] = defaultdict(list)
    def add(self, c: Claim) -> int:
        idx = len(self.claims)
        self.claims.append(c)
        self.by_subject[c.subject].append(idx)
        return idx
    def subject_items(self, subject: str) -> List[Claim]:
        return [self.claims[i] for i in self.by_subject.get(subject, [])]

# ----------  Generalized Knowledge (GK)  ----------
# Simple, explainable priors: frequency counts and EWMA outcome rates.

@dataclass
class GKEntry:
    count: int = 0
    ewma_value: float = 0.5     # prior probability for binary-ish outcomes
    ewma_alpha: float = 0.1

class GeneralizedKnowledge:
    def __init__(self):
        self.per_subject: Dict[str, GKEntry] = defaultdict(GKEntry)
    def update_with_observation(self, subject: str, numeric_outcome: Optional[float]):
        if numeric_outcome is None:
            return
        g = self.per_subject[subject]
        g.count += 1
        g.ewma_value = (1 - g.ewma_alpha) * g.ewma_value + g.ewma_alpha * float(numeric_outcome)
    def prior(self, subject: str) -> float:
        return self.per_subject[subject].ewma_value

# ----------  Subject Progress / Completion  ----------

@dataclass
class SubjectProgress:
    seen_items: int = 0
    distinct_sources: set = field(default_factory=set)
    completion_percent: float = 0.01  # start floor
    def update(self, new_source_ids: List[str]):
        self.seen_items += 1
        self.distinct_sources.update(new_source_ids)
        # naive heuristic: approach cap as items and sources diversify
        diversity = len(self.distinct_sources)
        # saturating function (1 - exp(-k*n)); k diminishes the growth rate
        k = 0.06 + 0.01 * min(diversity, 10)
        approx = (1 - math.exp(-k * self.seen_items)) * 100.0
        self.completion_percent = max(S_rules.min_comp_floor, min(S_rules.max_comp_cap, approx))

# ----------  Prediction & Evaluation  ----------

@dataclass
class PredictionRecord:
    subject: str
    scenario: Any
    prob: float          # model confidence (0..1)
    own: bool            # internally imagined?
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    correct: Optional[bool] = None
    brier: Optional[float] = None

class Predictor:
    def __init__(self, gk: GeneralizedKnowledge):
        self.gk = gk
        self.history: List[PredictionRecord] = []
        self.calibration_window: deque = deque(maxlen=256)
    def predict(self, subject: str, scenario: Any, extra_evidence: Optional[float]) -> float:
        # Combine GK prior with simple evidence via a convex blend
        prior = self.gk.prior(subject)
        if extra_evidence is None:
            return prior
        w = 0.35  # how much we trust the new evidence
        return max(0.01, min(0.99, (1 - w) * prior + w * extra_evidence))
    def log_prediction(self, p: PredictionRecord):
        self.history.append(p)
    def resolve(self, idx: int, observed: int):
        # observed should be 0/1 for this toy; adapt as needed
        p = self.history[idx]
        if p.resolved:
            return
        p.resolved = True
        p.correct = (observed == 1 and p.prob >= 0.5) or (observed == 0 and p.prob < 0.5)
        p.brier = (p.prob - observed) ** 2
        self.calibration_window.append(p.brier)

    def mean_brier(self) -> Optional[float]:
        if not self.calibration_window:
            return None
        return sum(self.calibration_window) / len(self.calibration_window)

# ----------  Replay Buffer  ----------

@dataclass
class ReplayEvent:
    kind: str                 # 'ingest', 'predict', 'resolve'
    subject: str
    label: Optional[float] = None      # for ingest / resolve
    prob: Optional[float] = None       # for predict / resolve
    correct: Optional[bool] = None     # for resolve
    timestamp: float = field(default_factory=time.time)

# ----------  Continuous Learner Orchestrator  ----------

class ContinuousLearner:
    def __init__(self, enable_logging: bool = True, enable_checkpoints: bool = True):
        self.sources = SourceRegistry()
        self.kb = KnowledgeBase()
        self.gk = GeneralizedKnowledge()
        self.predictor = Predictor(self.gk)
        self.progress: Dict[str, SubjectProgress] = defaultdict(SubjectProgress)
        self.event_count = 0
        self.last_reeval_event = 0
        self.last_checkpoint_event = 0
        self.total_reward = 0.0
        # Bias logs / cross-links
        self.bias_notes: List[str] = []
        self.links: List[Tuple[str, str, str]] = []  # (subject_a, relation, subject_b)
        
        # Logging setup
        self.enable_logging = enable_logging
        self.enable_checkpoints = enable_checkpoints and CHECKPOINT_AVAILABLE
        self.log_path = Path("logs/journal.log")
        self.replay: deque[ReplayEvent] = deque(maxlen=S_rules.replay_buffer_size)
        # simple per-subject pattern stats
        self.pattern_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "events": 0,
            "disagreements": 0,
            "last_label": None,
            "last_seen": 0.0,
        })

        if self.enable_logging:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                filename=str(self.log_path),
                level=logging.INFO,
                format='[%(asctime)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = None

    # --- Guardrails / Morals ---
    def enforce_guardrails(self, action_desc: str) -> None:
        # In this prototype we only simulate non-harmful read/eval.
        if not S_morals.never_harm_living:
            raise RuntimeError("Moral core misconfigured.")
        # Expand with domain checks if you add actions/experiments later.

    # --- Ingestion ---
    def ingest(self, subject: str, info: Any, label: Optional[int], source_names: List[str], own: bool = False):
        self.enforce_guardrails("ingest")
        source_ids = []
        for nm in source_names:
            # auto-add source if new
            existing = [sid for sid, s in self.sources.sources.items() if s.name == nm]
            sid = existing[0] if existing else self.sources.add(nm)
            source_ids.append(sid)

        claim = Claim(subject=subject, info=info, label=label, source_ids=source_ids, own=own)
        self.kb.add(claim)
        self.progress[subject].update(source_ids)

        # Update GK if label exists and is numeric-ish
        if label is not None and isinstance(label, (int, float)):
            self.gk.update_with_observation(subject, float(label))

        # reward small increments for procedural compliance (non-harmful, documented)
        self.total_reward += S_rules.reward_scale * 0.01
        self.event_count += 1
    
        # Track replay + simple disagreement pattern
        self.replay.append(ReplayEvent(
            kind="ingest",
            subject=subject,
            label=float(label) if isinstance(label, (int, float)) else None,
            timestamp=time.time()
        ))
        stats = self.pattern_stats[subject]
        stats["events"] += 1
        stats["last_seen"] = time.time()
        if label is not None and isinstance(label, (int, float)):
            if stats["last_label"] is not None and stats["last_label"] != label:
                stats["disagreements"] += 1
            stats["last_label"] = label

        # Log ingestion event
        if self.logger:
            self.logger.info(f"ACTION: add_claim | subject={subject} | sources={','.join(source_names)} | label={label} | delta_reward=+{S_rules.reward_scale * 0.01:.4f}")

        # periodic re-eval
        if self.event_count - self.last_reeval_event >= S_rules.reevaluation_interval_events:
            self.self_reflection()

        # periodic checkpointing
        if self.enable_checkpoints and (self.event_count - self.last_checkpoint_event >= S_rules.checkpoint_interval_events):
            try:
                create_checkpoint(self, label=f"event_{self.event_count}")
                self.last_checkpoint_event = self.event_count
                if self.logger:
                    self.logger.info(f"ACTION: checkpoint_created | event_count={self.event_count}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"ACTION: checkpoint_failed | error={str(e)}")

    # --- Skepticism (simple independence-aware trust) ---
    def skepticism(self, source_ids: List[str]) -> float:
        # Lower is better (less skeptical). Combine as: skepticism = product of (1 - trust_i)
        trusts = [self.sources.inherited_trust(sid) for sid in source_ids]
        if not trusts:
            return 1.0
        independent_conf = 1.0
        for t in trusts:
            independent_conf *= (0.9 * t + 0.1)  # soften extremes
        # skepticism drops as independent_conf rises
        return max(0.0, 1.0 - independent_conf)

    # --- Predictions ---
    def can_predict_external(self, subject: str) -> bool:
        return self.progress[subject].completion_percent >= (S_rules.external_prediction_after * 100.0)
    def can_predict_internal(self, subject: str) -> bool:
        return self.progress[subject].completion_percent >= (S_rules.allow_self_generated_scenarios_after * 100.0)

    def predict(self, subject: str, scenario: Any, evidence_hint: Optional[float], own: bool=False) -> int:
        self.enforce_guardrails("predict")
        if own and not self.can_predict_internal(subject):
            raise RuntimeError("Internal scenarios gated by completion threshold.")
        if not own and not self.can_predict_external(subject):
            raise RuntimeError("External prediction gated by completion threshold.")

        prob = self.predictor.predict(subject, scenario, evidence_hint)
        rec = PredictionRecord(subject=subject, scenario=scenario, prob=prob, own=own)
        self.predictor.log_prediction(rec)

        # small shaping reward for calibrated, cautious predictions (avoid overconfidence early)
        mean_brier = self.predictor.mean_brier()
        if mean_brier is not None:
            bonus = max(0.0, 0.25 - mean_brier) * S_rules.reward_scale
            self.total_reward += bonus

        self.replay.append(ReplayEvent(
            kind="predict",
            subject=subject,
            prob=prob,
            timestamp=rec.timestamp
        ))


        return len(self.predictor.history) - 1  # index to resolve later

    def resolve_prediction(self, idx: int, observed: int):
        self.enforce_guardrails("resolve_prediction")
        self.predictor.resolve(idx, observed)
        # reward correctness & calibration
        pr = self.predictor.history[idx]
        if pr.correct:
            self.total_reward += S_rules.reward_scale * 1.0
        # calibration reward (lower brier better)
        if pr.brier is not None:
            self.total_reward += S_rules.reward_scale * max(0.0, 0.2 - pr.brier)

        self.replay.append(ReplayEvent(
            kind="resolve",
            subject=pr.subject,
            label=float(observed),
            prob=pr.prob,
            correct=pr.correct,
            timestamp=pr.timestamp
        ))

        # Log prediction resolution
        if self.logger:
            result = "correct" if pr.correct else "incorrect"
            self.logger.info(f"ACTION: prediction_update | subject={pr.subject} | result={result} | brier={pr.brier:.4f}")

        # update source trust if scenario referenced sources later (you can expand)
        # (toy: nudge GK already updated during ingestion)

    # --- Self-reflection / Bias / Cross-links ---
    def self_reflection(self):
        # re-evaluate source trust using recent correctness (toy: gentle diffusion)
        for sid, s in self.sources.sources.items():
            # nudge toward mid unless proven otherwise (conservative)
            s.trust = 0.9 * s.trust + 0.1 * 0.5

        # note potential biases (toy: if a subject only has 1 source)
        bias_count_before = len(self.bias_notes)
        for subj, prog in self.progress.items():
            if len(prog.distinct_sources) <= 1 and prog.seen_items >= 3:
                self.bias_notes.append(f"[{time.ctime()}] Subject '{subj}' may be source-biased.")

        # pattern-based warnings (disagreement-heavy subjects)
        for subj, stats in self.pattern_stats.items():
            if stats["events"] >= 5:  # don’t warn too early
                ratio = stats["disagreements"] / max(1, stats["events"])
                if ratio > S_rules.disagreement_ratio_warn:
                    note = f"[{time.ctime()}] Subject '{subj}' shows high disagreement ratio={ratio:.2f}."
                    self.bias_notes.append(note)
                    # optional: register a link to indicate internal conflict pattern
                    self.links.append((subj, "high_disagreement", subj))
        
        # Log reflection event
        if self.logger:
            new_biases = len(self.bias_notes) - bias_count_before
            mean_brier = self.predictor.mean_brier()
            brier_str = f"{mean_brier:.4f}" if mean_brier is not None else "N/A"
            self.logger.info(
                f"ACTION: self_reflection | event_count={self.event_count} | "
                f"new_biases={new_biases} | mean_brier={brier_str}"
            )

        self.last_reeval_event = self.event_count

        # bounded shadow_eval (only after we have meaningful data)
        if self.event_count > 0 and (self.event_count % S_rules.shadow_eval_after_events) == 0:
            try:
                mean_brier = self.predictor.mean_brier()
                run_shadow_eval(
                    learner=self,
                    mean_brier=mean_brier,
                    replay=list(self.replay)
                )
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"ACTION: shadow_eval_failed | error={str(e)}")
        
        # Generate metrics report after reflection
        self._generate_metrics_report()

    # --- Internal Prediction and Imagination ---
    def generate_internal_scenario(self, subject: str) -> Any:
        """
        Very simple placeholder: generate a toy scenario for a subject.
        This should stay explainable and bounded.
        """
        # Example heuristic: just echo the subject with a timestamp
        return {
            "subject": subject,
            "hypothesis_time": time.time(),
            "note": "auto-generated internal scenario"
        }

    def imagine_and_predict(self, subject: str, evidence_hint: Optional[float] = None) -> Optional[int]:
        """
        Gated internal prediction: only allowed when completion passes threshold.
        Returns prediction index or None if not allowed.
        """
        if not self.can_predict_internal(subject):
            return None
        scenario = self.generate_internal_scenario(subject)
        return self.predict(subject, scenario, evidence_hint=evidence_hint, own=True)



    # --- Metrics Reporting ---
    def _generate_metrics_report(self):
        """Generate a JSON metrics report after reflection cycles."""
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate metrics
        total_predictions = len(self.predictor.history)
        resolved_predictions = [p for p in self.predictor.history if p.resolved]
        correct_predictions = [p for p in resolved_predictions if p.correct]
        
        accuracy = len(correct_predictions) / len(resolved_predictions) if resolved_predictions else 0.0
        mean_brier = self.predictor.mean_brier()
        
        metrics = {
            "timestamp": time.time(),
            "event_count": self.event_count,
            "total_reward": round(self.total_reward, 4),
            "accuracy": round(accuracy, 4) if resolved_predictions else None,
            "calibration_brier": round(mean_brier, 4) if mean_brier else None,
            "total_predictions": total_predictions,
            "resolved_predictions": len(resolved_predictions),
            "bias_count": len(self.bias_notes),
            "subjects_tracked": len(self.progress),
            "sources_count": len(self.sources.sources),
        }
        
        # Write report
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime(metrics["timestamp"]))
        report_path = reports_dir / f"metrics_{timestamp_str}.json"
        with open(report_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        if self.logger:
            accuracy_str = f"{accuracy:.4f}" if resolved_predictions else "N/A"
            self.logger.info(f"ACTION: metrics_report | path={report_path.name} | accuracy={accuracy_str}")

    # --- Utility / Inspect ---
    def subject_report(self, subject: str) -> Dict[str, Any]:
        prog = self.progress[subject]
        return dict(
            subject=subject,
            completion_percent=round(prog.completion_percent, 2),
            items=prog.seen_items,
            distinct_sources=len(prog.distinct_sources),
            gk_prior=round(self.gk.prior(subject), 3),
        )

# ----------------  Demo usage  ----------------
if __name__ == "__main__":
    agent = ContinuousLearner()

    # Ingest a few labeled facts for a toy binary subject
    agent.ingest("weather.rain_tomorrow", info={"city":"Austin"}, label=0, source_names=["NOAA"])
    agent.ingest("weather.rain_tomorrow", info={"city":"Austin"}, label=1, source_names=["LocalNews"])
    agent.ingest("weather.rain_tomorrow", info={"city":"Austin"}, label=0, source_names=["NOAA", "WXBlog"])

    print("REPORT A:", agent.subject_report("weather.rain_tomorrow"))

    # External prediction allowed?
    if agent.can_predict_external("weather.rain_tomorrow"):
        idx = agent.predict("weather.rain_tomorrow",
                            scenario={"city":"Austin","day":"tomorrow"},
                            evidence_hint=0.3, own=False)
        # Later, resolve when truth arrives:
        agent.resolve_prediction(idx, observed=0)

    print("REPORT B:", agent.subject_report("weather.rain_tomorrow"))
    print("Mean Brier:", agent.predictor.mean_brier())
    print("Bias notes:", agent.bias_notes)
    print("Total reward:", round(agent.total_reward, 3))
