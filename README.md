# Week 7 — Small Language Model Training

Started 2026-08-17. New project, fresh repo — no code inherited from Ship.

## What we know so far

- The week's project is training a small language model.
- Brief PDF: not yet downloaded (nothing matching Week 7 in Downloads as of kickoff).
  Drop it in `docs/` or Downloads and start the scoping pass from it — requirements
  come from the source document, never from memory of it.

## Conventions carried forward (earned the hard way in weeks 4–6)

- **No claim outlives the code.** Every "done" cites a file, test, run, or URL.
- Requirements ledger from day one (`docs/requirements.md`), statuses limited to
  MET / PARTIAL / MISSING / OWED — with OWED (blocked on owner) stated in every status.
- Evidence goes in dated folders: `evidence/YYYY-MM-DD/`.
- Training runs are experiments: log every run's config, seed, and metrics from run 1 —
  a result you can't reproduce is a rumor.
- Watch a check fail before trusting it green (applies to eval harnesses doubly).

## Layout (to be created as needed)

```
slm-week7/
├── README.md        ← this file
├── docs/            ← brief, requirements ledger, decisions
├── data/            ← datasets (gitignored if large)
├── src/             ← training + eval code
└── evidence/        ← dated proof artifacts
```
