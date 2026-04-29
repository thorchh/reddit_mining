# One-Shot Migration Scripts

Scripts that ran once and are done. Kept for reference only — do not re-run.

## Files

| File | When | What it did |
|------|------|-------------|
| `migrate_add_flairs.py` | Dec 1, 2025 | Added flair columns to the SQLite database schema |
| `backfill_flair.py` | Feb 4, 2026 | Backfilled physician-verified flair data for existing posts |
| `extract_consensus.py` | Dec 1, 2025 | Early one-off script to extract consensus from comments; superseded by `processors/consensus_extractor.py` |

These are safe to ignore. The database schema and data they modified are current.
