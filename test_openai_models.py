#!/usr/bin/env python3
"""
Phase 2: Test commercial (OpenAI) models on screened cases.

Sends each case to each model with each system prompt. Saves raw responses
(no evaluation — that's Phase 4).

Usage:
    python test_openai_models.py
    python test_openai_models.py --screening output/screening/latest.json
    python test_openai_models.py --cache output/responses/openai_responses_prev.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env.local")
load_dotenv(Path(__file__).parent / ".env")

sys.stdout.reconfigure(line_buffering=True)

from openai import OpenAI
from pipeline_config import OPENAI_MODELS, SYSTEM_PROMPTS, TESTING_WORKERS, RESPONSES_DIR

client = OpenAI()


def get_model_response(model_config: dict, system_prompt: str, user_message: str) -> str:
    """Get response from an OpenAI model."""
    use_new_param = any(x in model_config["model"] for x in ["gpt-5", "o1", "o3", "o4"])

    params = {
        "model": model_config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    if use_new_param:
        params["max_completion_tokens"] = 2048
    else:
        params["temperature"] = 1.0
        params["max_tokens"] = 2048

    response = client.chat.completions.create(**params)
    return response.choices[0].message.content


def run_single_test(model_config: dict, case: dict, prompt_name: str, system_prompt: str) -> dict:
    """Run one model on one case with one prompt."""
    user_message = f"{case['title']}\n\n{case['selftext']}"

    try:
        response_text = get_model_response(model_config, system_prompt, user_message)
    except Exception as e:
        return {
            "model": model_config["name"],
            "provider": "openai",
            "post_id": case["post_id"],
            "prompt_name": prompt_name,
            "response": f"ERROR: {e}",
            "error": str(e),
        }

    return {
        "model": model_config["name"],
        "provider": "openai",
        "post_id": case["post_id"],
        "prompt_name": prompt_name,
        "system_prompt": system_prompt,
        "response": response_text,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Test OpenAI models")
    parser.add_argument("--screening", type=str, default="output/screening/latest.json")
    parser.add_argument("--cache", type=str, default=None, help="Previous response file to skip already-tested combos")
    parser.add_argument("--workers", type=int, default=TESTING_WORKERS)
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load screening cases
    screening_path = Path(args.screening)
    if not screening_path.exists():
        print(f"Screening file not found: {screening_path}")
        sys.exit(1)

    cases = json.loads(screening_path.read_text())
    print(f"Loaded {len(cases)} screened cases")

    # Load cache
    cached_keys = set()
    cached_results = []
    if args.cache and Path(args.cache).exists():
        cached_results = json.loads(Path(args.cache).read_text())
        cached_keys = {(r["model"], r["post_id"], r["prompt_name"]) for r in cached_results if "error" not in r}
        print(f"Loaded {len(cached_results)} cached results ({len(cached_keys)} usable)")

    # Build task list
    tasks = []
    for case in cases:
        for model in OPENAI_MODELS:
            for prompt_name, system_prompt in SYSTEM_PROMPTS.items():
                key = (model["name"], case["post_id"], prompt_name)
                if key not in cached_keys:
                    tasks.append((model, case, prompt_name, system_prompt))

    print(f"\n{len(cases)} cases x {len(OPENAI_MODELS)} models x {len(SYSTEM_PROMPTS)} prompts")
    print(f"  Cached: {len(cached_results)}")
    print(f"  New to run: {len(tasks)}")

    results = list(cached_results)

    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_single_test, *t): t for t in tasks}
            done = 0
            for future in as_completed(futures):
                done += 1
                if done % 20 == 0:
                    print(f"  Completed {done}/{len(tasks)}...")
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"  Error: {e}")

    print(f"  Done. {len(results)} total results")

    # Save
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    output_file = RESPONSES_DIR / f"openai_responses_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
