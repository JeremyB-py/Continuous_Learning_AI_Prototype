"""Continuous Learner Core Module

This module provides the main entry point for the Continuous Learning AI Prototype.
It re-exports the ContinuousLearner class from CLAIP.py for convenience.
"""

# Import the full implementation from CLAIP
try:
    # Try absolute import first (when run as module)
    from src.CLAIP import (
        ContinuousLearner,
        SourceRegistry,
        KnowledgeBase,
        GeneralizedKnowledge,
        Predictor,
        SubjectProgress,
        Claim,
        PredictionRecord,
        StaticRules,
        S_rules,
    )
except ImportError:
    # Fall back to relative import (when run directly)
    from CLAIP import (
        ContinuousLearner,
        SourceRegistry,
        KnowledgeBase,
        GeneralizedKnowledge,
        Predictor,
        SubjectProgress,
        Claim,
        PredictionRecord,
        StaticRules,
        S_rules,
    )

# Re-export for convenience
__all__ = [
    'ContinuousLearner',
    'SourceRegistry',
    'KnowledgeBase',
    'GeneralizedKnowledge',
    'Predictor',
    'SubjectProgress',
    'Claim',
    'PredictionRecord',
    'StaticRules',
    'S_rules',
]

# If run directly, execute the demo
if __name__ == "__main__":
    try:
        from src.CLAIP import ContinuousLearner as CL
    except ImportError:
        from CLAIP import ContinuousLearner as CL
    
    agent = CL()
    
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
