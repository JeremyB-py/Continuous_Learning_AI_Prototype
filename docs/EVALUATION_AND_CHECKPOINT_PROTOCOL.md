# **Model Testing & Evaluation Protocol**

This document defines how every new module, rule, or learning update must be validated before integration into the main **Continuous Learner** system.
It provides procedures for *checkpointing, rollback, shadow evaluation,* and *metric reporting.*

---

## **1. Purpose**

To ensure that every change—code, rule, or parameter—can be **empirically verified**, **reversibly applied**, and **ethically safe** before it becomes part of the persistent learner state.

The testing process measures whether a change is **contributive** (improves performance or stability) or **detrimental** (reduces accuracy, alignment, or interpretability).

---

## **2. Overview of the Testing Pipeline**

| Stage                    | Description                                                  | Goal                                |
| ------------------------ | ------------------------------------------------------------ | ----------------------------------- |
| 1. Snapshot              | Create a checkpoint of the current system state.             | Preserve rollback point.            |
| 2. Shadow Evaluation     | Run the proposed change in parallel with the current system. | Compare metrics safely.             |
| 3. Contribution Analysis | Compute the Contribution Index from evaluation results.      | Quantify improvement or regression. |
| 4. Safety & Moral Audit  | Verify compliance with immutable moral rules.                | Detect violations.                  |
| 5. Promotion or Rollback | Promote change if contributive and safe; otherwise revert.   | Maintain system integrity.          |

---

## **3. Checkpointing & Rollback System**

### **3.1 Snapshot Creation**

Each major training or update cycle must begin with a snapshot:

```bash
/checkpoints/
    ├── core_state_<timestamp>.pkl
    ├── gk_state_<timestamp>.pkl
    ├── kb_state_<timestamp>.sqlite
    └── moral_core_hash.txt
```

* **Frequency:** Every N (e.g., 25–50) ingestion or reflection events.
* **Content:** All critical internal structures — KB, GK, progress maps, metrics, moral core checksum.
* **Format:** Serialized (`pickle`, `json`, or `sqlite`) with version header and timestamp.

### **3.2 Journaled Updates**

Each new write is logged in `journal.log`:

```
[time] ACTION: add_claim | subject=weather.rain | source=NOAA | delta_reward=+0.004
[time] ACTION: prediction_update | subject=weather.rain | result=correct
```

All operations are **append-only**.
Reverting = replaying journal until one step before undesired update.

### **3.3 Rollback Procedure**

1. Halt all running processes.
2. Select rollback point:

   ```bash
   python restore_checkpoint.py --to core_state_YYYYMMDD_HHMM.pkl
   ```
3. Verify moral core checksum matches `moral_core_hash.txt`.
4. Resume from restored state.

---

## **4. Shadow Evaluation Framework**

### **4.1 Principle**

All new logic runs in *parallel* with the current stable agent using the same input stream, but only the *shadow instance* is modified.

### **4.2 Workflow**

```
               ┌───────────────┐
               │ Input Stream  │
               └──────┬────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
  Stable Agent (A)        Shadow Agent (B)
  - uses existing code     - includes new rule/module
  - updates real state     - isolated sandbox
          │                       │
          └───────────┬───────────┘
                      │
             Metrics Comparison
```

**Evaluation Duration:** until both agents process ≥ N identical events.

---

## **5. Contribution Index**

A single scalar metric summarizing whether a change should be promoted.

[
C = α(Δ\text{Accuracy}) - β(\text{Moral Violations}) + γ(Δ\text{Uncertainty Reduction}) - δ(Δ\text{Bias Count})
]

| Symbol | Meaning                                            | Suggested Default |
| ------ | -------------------------------------------------- | ----------------- |
| α      | Weight for performance improvement                 | 1.0               |
| β      | Penalty for moral violations                       | 5.0               |
| γ      | Reward for reduced uncertainty / calibration error | 0.8               |
| δ      | Penalty for increased bias                         | 0.5               |

**Promotion Criteria:**

* ( C > 0 )
* No recorded moral violation
* System remains within calibration tolerance (Brier ≤ baseline × 1.1)

---

## **6. Safety & Moral Audit**

Before any integration:

1. Run automated **Moral Unit Tests** (e.g., ensure “Do not purposely deceive” never fails).
2. Run at least one **Random Moral Audit**, sampling recent predictions and verifying moral compliance.
3. Confirm **Moral Core Integrity Hash** matches the stored version.
4. Document any temporary exceptions with justification and expiration date.

**Example Audit Log**

```
[2025-10-18T20:41Z]
Test: harm_prevention .................. PASS
Test: deception_prevention ............. PASS
Test: reasonable_outweighs_unreasonable  PASS
Hash: 9f7c1a04b... verified
```

---

## **7. Promotion Decision Protocol**

| Outcome                 | Action                              | Notes                           |
| ----------------------- | ----------------------------------- | ------------------------------- |
| Contributive & Safe     | Promote to main branch              | Merge and log version bump.     |
| Contributive but Unsafe | Keep in sandbox, revise moral layer | Require external review.        |
| Detrimental             | Roll back immediately               | Add to Lessons Learned section. |

All promotions must be accompanied by:

* Updated changelog entry
* Updated `LIMITATIONS_AND_SAFEGUARDS.md` if new risk category arises
* Recalculated baseline metrics

---

## **8. Continuous Evaluation Metrics**

Each evaluation cycle produces a summary report:

| Metric              | Description                       | Target                 |
| ------------------- | --------------------------------- | ---------------------- |
| Accuracy            | Correct vs total predictions      | ≥ previous baseline    |
| Calibration (Brier) | Confidence vs outcome alignment   | ↓ over time            |
| Moral Violations    | Any breach of core rules          | 0 tolerated            |
| Bias Count          | Detected skew in source diversity | ↓ over time            |
| Reflection Ratio    | Reflections per ingestions        | maintain fixed ratio   |
| Core Drift          | Δ in GK_conf compared to baseline | ≤ threshold (e.g., 2%) |

Reports are stored in `/reports/metrics_<timestamp>.json`.

---

## **9. Human Oversight and Version Control**

* Every promotion or rollback must be reviewed and approved by a human operator (or later, a review committee).
* All system-level changes require pull requests, not direct commits.
* Each merge must include:

  * A summary of metric outcomes.
  * Proof of passing moral tests.
  * Signed acknowledgment of compliance.

---

## **10. Recovery and Lessons Learned**

When a regression or moral failure occurs:

1. Roll back immediately to the last known safe checkpoint.
2. Document:

   * Circumstances
   * Root cause
   * Lessons learned
   * Updated safeguards
3. Append the entry to `/logs/failures.md`.

---

## **11. Automation Plan (Future)**

Future versions will implement:

* Automatic checkpointing daemons
* Shadow-evaluation orchestrator scripts
* Dashboard visualizations for Contribution Index trends
* Optional integration with CI/CD (GitHub Actions) for reproducible testing

---

*This protocol is mandatory for all future iterations of the Continuous Learner project.
Any code merged without adherence must be considered experimental and unverified.*