#!/bin/bash
#
# Adaptive parallel vLLM model runner for CARC.
# Auto-detects available GPUs and schedules models in batches that fit.
# Works with 2, 4, or 8 GPUs — runs as many models in parallel as possible.
#
# Usage:
#   bash run_models_parallel.sh                              # all cases
#   bash run_models_parallel.sh --limit 1000                 # first 1000 cases
#   bash run_models_parallel.sh --post-ids 1qjlode,1q9q1pk  # specific cases
#

set -euo pipefail

# ── Environment setup ──────────────────────────────────────────
module purge
module load gcc/13.3.0 python/3.11.9 cuda/12.6.3

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/../vllm_env"
SCREENING="$PROJECT_DIR/output/screening/screening_final.json"

export HF_HOME="/scratch1/$USER/.cache/huggingface"

source "$VENV_DIR/bin/activate"

# ── Models: "model_id|display_name|tp" ─────────────────────────
ALL_MODELS=(
    "Qwen/Qwen2.5-7B-Instruct|Qwen2.5-7B|1"
    "Qwen/Qwen2.5-14B-Instruct|Qwen2.5-14B|1"
    "Qwen/Qwen3-30B-A3B|Qwen3-30B-A3B|2"
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503|Mistral-Small-24B|2"
    "microsoft/phi-4|Phi-4|1"
)

EXTRA_ARGS="$*"
BASE_PORT=31010

# ── Detect GPUs ────────────────────────────────────────────────
NUM_GPUS=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
echo "======================================"
echo "Adaptive parallel vLLM runner"
echo "GPUs available: $NUM_GPUS"
echo "Models: ${#ALL_MODELS[@]}"
echo "Screening: $SCREENING"
echo "Extra args: $EXTRA_ARGS"
echo "======================================"

# ── Schedule models into batches that fit available GPUs ───────
# Greedy bin-packing: add models to current batch until GPUs full
BATCHES=()       # semicolon-separated entries per batch
BATCH_GPUS=()    # GPU count per batch

current_batch=""
current_gpus=0

for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r MODEL_ID DISPLAY_NAME TP <<< "$entry"

    if (( current_gpus + TP > NUM_GPUS )); then
        # Current batch is full, save it and start new one
        BATCHES+=("$current_batch")
        BATCH_GPUS+=("$current_gpus")
        current_batch="$entry"
        current_gpus=$TP
    else
        if [ -z "$current_batch" ]; then
            current_batch="$entry"
        else
            current_batch="$current_batch;$entry"
        fi
        current_gpus=$((current_gpus + TP))
    fi
done
# Don't forget the last batch
if [ -n "$current_batch" ]; then
    BATCHES+=("$current_batch")
    BATCH_GPUS+=("$current_gpus")
fi

echo ""
echo "Scheduled ${#BATCHES[@]} batch(es):"
for i in "${!BATCHES[@]}"; do
    echo "  Batch $((i+1)) (${BATCH_GPUS[$i]} GPUs): $(echo "${BATCHES[$i]}" | tr ';' '\n' | while IFS='|' read -r _ name _; do echo -n "$name "; done)"
done

# ── Helper functions ───────────────────────────────────────────
declare -A VLLM_PIDS

cleanup() {
    echo ""
    echo "Cleaning up vLLM servers..."
    for name in "${!VLLM_PIDS[@]}"; do
        kill "${VLLM_PIDS[$name]}" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    VLLM_PIDS=()
}
trap cleanup EXIT

wait_for_vllm() {
    local port=$1
    local name=$2
    local timeout=600
    local start=$SECONDS
    while true; do
        if curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; then
            echo "  [READY] $name on port $port ($(( SECONDS - start ))s)"
            return 0
        fi
        if (( SECONDS - start > timeout )); then
            echo "  [FAIL] $name on port $port (timeout after ${timeout}s)"
            return 1
        fi
        sleep 5
    done
}

ALL_FAILED=()
ALL_TEST_FAILED=()

# ── Run each batch ─────────────────────────────────────────────
for batch_idx in "${!BATCHES[@]}"; do
    echo ""
    echo "══════════════════════════════════════"
    echo "BATCH $((batch_idx+1))/${#BATCHES[@]} (${BATCH_GPUS[$batch_idx]} GPUs)"
    echo "══════════════════════════════════════"

    # Parse batch entries
    IFS=';' read -ra BATCH_ENTRIES <<< "${BATCHES[$batch_idx]}"

    # Start vLLM servers for this batch
    gpu_offset=0
    port_offset=0
    declare -A TEST_PIDS
    READY=()

    for entry in "${BATCH_ENTRIES[@]}"; do
        IFS='|' read -r MODEL_ID DISPLAY_NAME TP <<< "$entry"
        PORT=$((BASE_PORT + port_offset))
        port_offset=$((port_offset + 1))

        # Build CUDA_VISIBLE_DEVICES
        gpu_list=""
        for ((g=0; g<TP; g++)); do
            if [ -n "$gpu_list" ]; then gpu_list="$gpu_list,"; fi
            gpu_list="$gpu_list$((gpu_offset + g))"
        done
        gpu_offset=$((gpu_offset + TP))

        echo "  Starting $DISPLAY_NAME (tp=$TP, GPUs=$gpu_list) on port $PORT..."
        CUDA_VISIBLE_DEVICES=$gpu_list vllm serve "$MODEL_ID" \
            --tensor-parallel-size "$TP" \
            --port "$PORT" \
            --disable-log-requests \
            > "vllm_${DISPLAY_NAME}.log" 2>&1 &
        VLLM_PIDS[$DISPLAY_NAME]=$!
    done

    # Wait for all servers in this batch
    echo ""
    echo "  Waiting for servers..."
    port_offset=0
    for entry in "${BATCH_ENTRIES[@]}"; do
        IFS='|' read -r MODEL_ID DISPLAY_NAME TP <<< "$entry"
        PORT=$((BASE_PORT + port_offset))
        port_offset=$((port_offset + 1))

        if wait_for_vllm "$PORT" "$DISPLAY_NAME"; then
            READY+=("$DISPLAY_NAME|$PORT")
        else
            ALL_FAILED+=("$DISPLAY_NAME")
            kill "${VLLM_PIDS[$DISPLAY_NAME]}" 2>/dev/null || true
            unset "VLLM_PIDS[$DISPLAY_NAME]"
        fi
    done

    # Run tests in parallel for this batch
    echo ""
    echo "  Running tests..."
    for ready_entry in "${READY[@]}"; do
        IFS='|' read -r DISPLAY_NAME PORT <<< "$ready_entry"

        # Auto-detect latest cache file (checkpoint or final) for this model
        CACHE_ARG=""
        LATEST_CACHE=""
        for cf in "$PROJECT_DIR"/output/responses/vllm_${DISPLAY_NAME}_*.json; do
            [ -f "$cf" ] && LATEST_CACHE="$cf"
        done
        if [ -n "$LATEST_CACHE" ]; then
            CACHE_ARG="--cache $LATEST_CACHE"
            echo "    Using cache for $DISPLAY_NAME: $(basename "$LATEST_CACHE")"
        fi

        echo "    Launching test for $DISPLAY_NAME..."
        python "$PROJECT_DIR/pipeline/test_vllm_models.py" \
            --url "http://localhost:$PORT/v1" \
            --display-name "$DISPLAY_NAME" \
            --screening "$SCREENING" \
            $CACHE_ARG \
            $EXTRA_ARGS \
            > "test_${DISPLAY_NAME}.log" 2>&1 &
        TEST_PIDS[$DISPLAY_NAME]=$!
    done

    # Wait for tests to complete
    for name in "${!TEST_PIDS[@]}"; do
        if wait "${TEST_PIDS[$name]}"; then
            echo "    [DONE] $name"
        else
            echo "    [FAIL] $name (see test_${name}.log)"
            ALL_TEST_FAILED+=("$name")
        fi
    done
    unset TEST_PIDS

    # Kill vLLM servers for this batch before next batch
    echo "  Stopping servers..."
    for name in "${!VLLM_PIDS[@]}"; do
        kill "${VLLM_PIDS[$name]}" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    VLLM_PIDS=()
    sleep 5
done

# ── Summary ────────────────────────────────────────────────────
echo ""
echo "======================================"
echo "All batches complete."
if [ ${#ALL_FAILED[@]} -gt 0 ]; then
    echo "Models that failed to load: ${ALL_FAILED[*]}"
fi
if [ ${#ALL_TEST_FAILED[@]} -gt 0 ]; then
    echo "Tests that failed: ${ALL_TEST_FAILED[*]}"
fi
if [ ${#ALL_FAILED[@]} -eq 0 ] && [ ${#ALL_TEST_FAILED[@]} -eq 0 ]; then
    echo "All models succeeded."
fi
echo ""
echo "Logs:"
for entry in "${ALL_MODELS[@]}"; do
    IFS='|' read -r MODEL_ID DISPLAY_NAME TP <<< "$entry"
    echo "  vLLM:  vllm_${DISPLAY_NAME}.log"
    echo "  Test:  test_${DISPLAY_NAME}.log"
done
echo "Results: output/responses/vllm_*.json"
echo "======================================"
