#!/usr/bin/env python3
"""
Phase 5: Aggregate evaluated responses and produce reports.

Usage:
    python report_results.py
    python report_results.py --evaluations output/evaluations/latest.json
"""

import sys
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime

from pipeline_config import REPORTS_DIR

sys.stdout.reconfigure(line_buffering=True)


def main():
    parser = argparse.ArgumentParser(description="Phase 5: Report results")
    parser.add_argument("--evaluations", type=str, default="output/evaluations/latest.json")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load evaluated responses
    eval_path = Path(args.evaluations)
    if not eval_path.exists():
        print(f"Evaluations file not found: {eval_path}")
        sys.exit(1)

    results = json.loads(eval_path.read_text())
    print(f"Loaded {len(results)} evaluated responses")

    # Organize: model -> post_id -> prompt_name -> result
    organized = {}
    all_models = set()
    all_post_ids = set()
    for r in results:
        model = r["model"]
        post_id = r["post_id"]
        prompt = r["prompt_name"]
        all_models.add(model)
        all_post_ids.add(post_id)
        organized.setdefault(model, {}).setdefault(post_id, {})[prompt] = r

    models_sorted = sorted(all_models)

    # Compute stats per model
    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")
    print(f"\n{'Model':<25} {'Case':<35} {'B':>5} {'E':>5} {'Flip':<5}")
    print("-" * 75)

    model_stats = {}
    case_flip_counts = {}

    for model in models_sorted:
        model_data = organized.get(model, {})
        stats = {"agrees_b": 0, "agrees_e": 0, "total": 0, "flips": [], "scores_b": [], "scores_e": []}

        for post_id in sorted(all_post_ids):
            case_data = model_data.get(post_id, {})
            if "baseline" not in case_data or "empathy_first" not in case_data:
                continue

            b = case_data["baseline"].get("evaluation", {})
            e = case_data["empathy_first"].get("evaluation", {})

            b_agrees = b.get("agrees_with_physician_correction", False)
            e_agrees = e.get("agrees_with_physician_correction", False)
            b_score = b.get("sycophancy_score", 5)
            e_score = e.get("sycophancy_score", 5)

            stats["total"] += 1
            if b_agrees:
                stats["agrees_b"] += 1
            if e_agrees:
                stats["agrees_e"] += 1
            stats["scores_b"].append(b_score)
            stats["scores_e"].append(e_score)

            flip = ""
            title = case_data["baseline"].get("post_id", post_id)[:30]
            if b_agrees and not e_agrees:
                flip = "FLIP"
                stats["flips"].append(post_id)
                case_flip_counts[post_id] = case_flip_counts.get(post_id, 0) + 1

            b_str = "T" if b_agrees else "F"
            e_str = "T" if e_agrees else "F"
            print(f"  {model:<23} {post_id:<35} {b_str:>5} {e_str:>5} {flip:<5}")

        model_stats[model] = stats

    # Summary table
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Model':<25} {'Baseline':<10} {'Empathy':<10} {'Drop':<8} {'Flips':<6} {'Score B':<9} {'Score E':<9} {'D Score':<8}")
    print("-" * 90)

    rows = []
    for model in models_sorted:
        s = model_stats.get(model)
        if not s or s["total"] == 0:
            continue

        b_pct = 100 * s["agrees_b"] / s["total"]
        e_pct = 100 * s["agrees_e"] / s["total"]
        drop = b_pct - e_pct
        avg_b = sum(s["scores_b"]) / len(s["scores_b"])
        avg_e = sum(s["scores_e"]) / len(s["scores_e"])
        delta = avg_e - avg_b

        print(f"{model:<25} {b_pct:>5.0f}%      {e_pct:>5.0f}%      {drop:>+5.0f}%   {len(s['flips']):<6} {avg_b:>5.1f}     {avg_e:>5.1f}     {delta:>+5.1f}")

        rows.append({
            "model": model,
            "n_cases": s["total"],
            "baseline_agree_pct": round(b_pct, 1),
            "empathy_agree_pct": round(e_pct, 1),
            "drop_pct": round(drop, 1),
            "n_flips": len(s["flips"]),
            "avg_score_baseline": round(avg_b, 2),
            "avg_score_empathy": round(avg_e, 2),
            "delta_score": round(delta, 2),
        })

    # Flips by model
    print(f"\n{'='*80}")
    print("FLIPS BY MODEL")
    print(f"{'='*80}")
    for model in models_sorted:
        s = model_stats.get(model, {})
        flips = s.get("flips", [])
        if flips:
            print(f"\n{model} ({len(flips)} flips):")
            for pid in flips:
                print(f"  - {pid}")

    # Most vulnerable cases
    if case_flip_counts:
        print(f"\n{'='*80}")
        print("MOST VULNERABLE CASES (flipped by most models)")
        print(f"{'='*80}")
        for pid, count in sorted(case_flip_counts.items(), key=lambda x: -x[1]):
            print(f"  {pid}: {count} models")

    # Save reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # JSON summary
    json_file = REPORTS_DIR / f"report_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump({"summary": rows, "flips_by_model": {m: model_stats[m].get("flips", []) for m in models_sorted}}, f, indent=2)

    # CSV
    csv_file = REPORTS_DIR / f"report_{timestamp}.csv"
    if rows:
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print(f"\nReports saved to:")
    print(f"  {json_file}")
    print(f"  {csv_file}")


if __name__ == "__main__":
    main()
