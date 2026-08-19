"""Teacher-distillation data pipeline for "Benefits Notices, Explained" (M5).

Modules:
    notices   - synthetic notice generator (templates + programmatic variation)
    students  - user-turn (dialog script) generator, incl. contrast pairs
    teacher   - teacher calls + deterministic filter (src.checker) + repair loop
    run_datagen - CLI orchestrator; writes train.jsonl / rejected.jsonl /
                  STATS.json / DATASET.md
"""
