#!/bin/bash
#
# Automated vLLM model runner for CARC.
# Runs inside an existing Slurm GPU allocation (salloc/srun).
# For each model: starts vLLM, waits for readiness, runs tests, kills vLLM.
#
# Usage:
#   bash run_models.sh                              # all 1000 cases
#   bash run_models.sh --limit 100                  # first 100 cases
#   bash run_models.sh --post-ids 1qjlode,1q9q1pk   # specific cases
#

set -euo pipefail

# ── Environment setup ──────────────────────────────────────────
module purge
module load gcc/13.3.0 python/3.11.9 cuda/12.6.3

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/../vllm_env"
SCREENING="$PROJECT_DIR/output/screening/screening_final.json"
PORT=31010

export HF_HOME="/scratch1/$USER/.cache/huggingface"

source "$VENV_DIR/bin/activate"

# ── Models to test ─────────────────────────────────────────────
# Format: "model_id|display_name|tensor_parallel_size"
MODELS=(
    "Qwen/Qwen2.5-7B-Instruct|Qwen2.5-7B|1"
    "Qwen/Qwen2.5-14B-Instruct|Qwen2.5-14B|1"
    "Qwen/Qwen3-30B-A3B|Qwen3-30B-A3B|2"
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503|Mistral-Small-24B|2"
    "microsoft/phi-4|Phi-4|1"
)

# ── Pass extra args through (--limit, --post-ids, --cache) ─────
EXTRA_ARGS="$*"

# ── Helper: wait for vLLM to be ready ──────────────────────────
wait_for_vllm() {
    local timeout=600  # 10 minutes
    local start=$SECONDS
    echo "  Waiting for vLLM on port $PORT..."
    while true; do
        if curl -s "http://localhost:$PORT/v1/models" > /dev/null 2>&1; then
            echo "  vLLM ready ($(( SECONDS - start ))s)"
            return 0
        fi
        if (( SECONDS - start > timeout )); then
            echo "  ERROR: vLLM failed to start within ${timeout}s"
            return 1
        fi
        sleep 5
    done
}

# ── Main loop ──────────────────────────────────────────────────
echo "======================================"
echo "Multi-model vLLM test runner"
echo "Models: ${#MODELS[@]}"
echo "Screening: $SCREENING"
echo "Extra args: $EXTRA_ARGS"
echo "======================================"

TOTAL=${#MODELS[@]}
CURRENT=0
FAILED=()

for entry in "${MODELS[@]}"; do
    IFS='|' read -r MODEL_ID DISPLAY_NAME TP <<< "$entry"
    CURRENT=$((CURRENT + 1))

    echo ""
    echo "══════════════════════════════════════"
    echo "[$CURRENT/$TOTAL] $DISPLAY_NAME"
    echo "  Model: $MODEL_ID"
    echo "  Tensor parallel: $TP"
    echo "══════════════════════════════════════"

    # Start vLLM server in background
    echo "  Starting vLLM server..."
    vllm serve "$MODEL_ID" \
        --tensor-parallel-size "$TP" \
        --port "$PORT" \
        --disable-log-requests \
        > "vllm_${DISPLAY_NAME}.log" 2>&1 &
    VLLM_PID=$!

    # Wait for readiness
    if ! wait_for_vllm; then
        echo "  SKIPPING $DISPLAY_NAME (failed to start)"
        FAILED+=("$DISPLAY_NAME")
        kill $VLLM_PID 2>/dev/null || true
        wait $VLLM_PID 2>/dev/null || true
        continue
    fi

    # Run test
    echo "  Running test_vllm_models.py..."
    python "$PROJECT_DIR/test_vllm_models.py" \
        --url "http://localhost:$PORT/v1" \
        --display-name "$DISPLAY_NAME" \
        --screening "$SCREENING" \
        $EXTRA_ARGS \
    || {
        echo "  WARNING: test_vllm_models.py exited with error for $DISPLAY_NAME"
        FAILED+=("$DISPLAY_NAME")
    }

    # Kill vLLM
    echo "  Stopping vLLM (PID $VLLM_PID)..."
    kill $VLLM_PID 2>/dev/null || true
    wait $VLLM_PID 2>/dev/null || true
    sleep 5

    echo "  Done with $DISPLAY_NAME"
done

# ── Summary ────────────────────────────────────────────────────
echo ""
echo "======================================"
echo "All models complete."
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "FAILED: ${FAILED[*]}"
else
    echo "All models succeeded."
fi
echo "======================================"
