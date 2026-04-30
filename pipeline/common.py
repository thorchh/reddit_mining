"""Shared utilities for pipeline scripts."""

import json
from pathlib import Path


def load_responses(responses_dir: Path) -> list:
    """Load all vLLM response files, deduplicate keeping latest by timestamp."""
    all_responses = []
    for f in sorted(responses_dir.glob("vllm_*.json")):
        data = json.loads(f.read_text())
        all_responses.extend(data)

    seen = {}
    for r in all_responses:
        if "error" in r:
            continue
        key = (r["model"], r["post_id"], r["prompt_name"])
        if key not in seen or r.get("timestamp", "") > seen[key].get("timestamp", ""):
            seen[key] = r
    return list(seen.values())
