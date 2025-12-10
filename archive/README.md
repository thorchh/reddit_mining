# Archived Scripts

These scripts have been deprecated and replaced by `run_sycophancy_evaluation.py`.

## Archived Files

### `evaluate_sycophancy.py` (Original)
**Deprecated**: 2025-12-10  
**Reason**: Did not validate consensus before testing. Used naive top comment as ground truth.

**What it did**:
- 3-stage pipeline: Generate prompt → Test VLM → Verify sycophancy
- No consensus validation
- No control testing

**Replaced by**: `run_sycophancy_evaluation.py`

---

### `evaluate_sycophancy_enhanced.py` (Enhanced Version)
**Deprecated**: 2025-12-10  
**Reason**: Complex implementation with redundant verification. Superseded by simpler, more robust design.

**What it did**:
- Added pre-evaluation verification step
- Added control testing
- Used separate verifiers (consensus_verifier + response_comparer)
- More complex than needed

**Replaced by**: `run_sycophancy_evaluation.py`

---

### `analyze_sycophancy_results.py` (Post-hoc Analysis)
**Deprecated**: 2025-12-10  
**Reason**: Designed for analyzing old results without consensus validation. No longer needed with new pipeline.

**What it did**:
- Analyzed existing evaluation results
- Added correctness verification after the fact
- Used ConsensusVerifier on already-evaluated posts

**Note**: May be useful for analyzing legacy results, but not part of main pipeline.

---

## Why These Were Replaced

### Problem 1: No Consensus Validation
The original scripts used the top comment as "ground truth" without verification. This caused issues:
- Top comment might not represent consensus
- Ground truth and wrong answer could be the same thing with different names
- No check for semantic similarity

### Problem 2: No Control Testing
Without a control condition (neutral prompt), we couldn't prove sycophantic prompts actually influenced the VLM.

### Problem 3: Complex Architecture
The enhanced version had:
- Multiple separate verifiers
- Redundant verification steps
- More moving parts than necessary

### Solution: `run_sycophancy_evaluation.py`

The new script is:
- **Simpler**: Single script, single verifier
- **More robust**: Validates consensus before testing
- **Complete**: Includes control + sycophantic testing
- **Efficient**: One LLM call for verification instead of multiple

---

## Migration Guide

If you have results from old scripts:

### Old Script → New Script

```bash
# Old way (deprecated)
python evaluate_sycophancy.py \
  --checkpoint checkpoint.json

# New way
python run_sycophancy_evaluation.py \
  --checkpoint checkpoint.json
```

### Analyzing Old Results

If you have results from `evaluate_sycophancy.py`, you can use the archived `analyze_sycophancy_results.py` to add correctness verification:

```bash
python archive/analyze_sycophancy_results.py \
  --results output/old_results.json
```

**Note**: This is only for legacy data. New evaluations should use `run_sycophancy_evaluation.py` which includes validation and control testing from the start.

---

## Technical Details

### Old Architecture (Deprecated)
```
Load posts → Generate prompt → Test VLM → Verify sycophancy
```

Problems:
- No validation that ground truth ≠ wrong answer
- No control condition
- Can't measure true impact

### New Architecture (Current)
```
Load posts → Validate consensus (LLM analyzes all comments)
           ↓
           Filter valid posts
           ↓
           Generate prompt → Test VLM (control + sycophantic)
           ↓
           Verify both responses (single LLM call)
```

Benefits:
- Ensures data quality
- Measures true impact
- Simpler code

---

## Should I Use These?

**No.** Use `run_sycophancy_evaluation.py` instead.

These scripts are kept for:
1. Historical reference
2. Analyzing legacy results
3. Understanding design evolution

---

## Questions?

See the main README.md for current pipeline documentation.
