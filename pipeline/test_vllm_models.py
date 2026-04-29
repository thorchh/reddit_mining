#!/usr/bin/env python3
"""
Phase 3: Test open-source models via vLLM on screened cases.

Connects to a running vLLM server (OpenAI-compatible API) and tests models
with the same prompts as Phase 2. Output format is identical.

Usage:
    python test_vllm_models.py --url http://c05-03:31010/v1
    python test_vllm_models.py --url http://c05-03:31010/v1 --screening output/screening/latest.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")
load_dotenv(Path(__file__).parent.parent / ".env")

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from pipeline_config import SYSTEM_PROMPTS, RESPONSES_DIR


def get_vllm_response(client: OpenAI, model_name: str, system_prompt: str, user_message: str) -> str:
    """Get response from a vLLM-served model (OpenAI-compatible API)."""
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=1.0,
        max_tokens=4096,
    )
    raw = response.choices[0].message.content
    # Strip thinking tags (Qwen3)
    if "<think>" in raw and "</think>" in raw:
        raw = raw.split("</think>")[-1].strip()
    return raw


def run_single_test(client: OpenAI, model_name: str, display_name: str,
                    case: dict, prompt_name: str, system_prompt: str) -> dict:
    """Run one test case."""
    user_message = f"{case['title']}\n\n{case['selftext']}"

    try:
        response_text = get_vllm_response(client, model_name, system_prompt, user_message)
    except Exception as e:
        return {
            "model": display_name,
            "provider": "vllm",
            "post_id": case["post_id"],
            "prompt_name": prompt_name,
            "response": f"ERROR: {e}",
            "error": str(e),
        }

    return {
        "model": display_name,
        "provider": "vllm",
        "post_id": case["post_id"],
        "prompt_name": prompt_name,
        "system_prompt": system_prompt,
        "response": response_text,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 3: Test vLLM models")
    parser.add_argument("--url", type=str, required=True, help="vLLM server URL (e.g. http://c05-03:31010/v1)")
    parser.add_argument("--model-name", type=str, default=None, help="Model name on the server (auto-detected if not set)")
    parser.add_argument("--display-name", type=str, default=None, help="Name for results (e.g. Qwen2.5-7B)")
    parser.add_argument("--screening", type=str, default="output/screening/latest.json")
    parser.add_argument("--cache", type=str, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="Only test first N screening cases")
    parser.add_argument("--post-ids", type=str, default=None, help="Comma-separated post_ids to test (e.g. 1qjlode,1q9q1pk)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Connect to vLLM server
    vllm_client = OpenAI(base_url=args.url, api_key="not-needed")

    # Auto-detect model name
    model_name = args.model_name
    if not model_name:
        models = vllm_client.models.list()
        model_name = models.data[0].id
        print(f"Auto-detected model: {model_name}")

    display_name = args.display_name or model_name.split("/")[-1]

    # Load screening cases
    screening_path = Path(args.screening)
    if not screening_path.exists():
        print(f"Screening file not found: {screening_path}")
        sys.exit(1)

    cases = json.loads(screening_path.read_text())
    print(f"Loaded {len(cases)} screened cases")

    # Filter cases by --post-ids or --limit
    if args.post_ids:
        post_id_set = set(args.post_ids.split(","))
        cases = [c for c in cases if c["post_id"] in post_id_set]
        missing = post_id_set - {c["post_id"] for c in cases}
        if missing:
            print(f"WARNING: post_ids not found in screening: {missing}")
        print(f"Filtered to {len(cases)} cases by post_id")
    elif args.limit:
        cases = cases[:args.limit]
        print(f"Limited to first {len(cases)} cases")

    # Load cache
    cached_keys = set()
    cached_results = []
    if args.cache and Path(args.cache).exists():
        cached_results = json.loads(Path(args.cache).read_text())
        cached_keys = {(r["model"], r["post_id"], r["prompt_name"]) for r in cached_results if "error" not in r}
        print(f"Loaded {len(cached_results)} cached results")

    # Build task list
    tasks = []
    for case in cases:
        for prompt_name, system_prompt in SYSTEM_PROMPTS.items():
            key = (display_name, case["post_id"], prompt_name)
            if key not in cached_keys:
                tasks.append((vllm_client, model_name, display_name, case, prompt_name, system_prompt))

    print(f"\n{len(cases)} cases x {len(SYSTEM_PROMPTS)} prompts")
    print(f"  Cached: {len(cached_results)}")
    print(f"  New to run: {len(tasks)}")

    results = list(cached_results)

    if tasks:
        safe_name = display_name.replace("/", "_")
        checkpoint_file = RESPONSES_DIR / f"vllm_{safe_name}_{timestamp}_checkpoint.json"

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_single_test, *t): t for t in tasks}
            done = 0
            for future in as_completed(futures):
                done += 1
                if done % 10 == 0:
                    print(f"  Completed {done}/{len(tasks)}...")
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"  Error: {e}")

                # Checkpoint every 50
                if done % 50 == 0:
                    with open(checkpoint_file, "w") as f:
                        json.dump(results, f)
                    print(f"  [checkpoint saved: {len(results)} results]")

    print(f"  Done. {len(results)} total results")

    # Save
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = display_name.replace("/", "_")
    output_file = RESPONSES_DIR / f"vllm_{safe_name}_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
