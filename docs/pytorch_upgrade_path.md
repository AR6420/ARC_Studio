# PyTorch sm_120 (Blackwell) Upgrade Path

This document tracks the upgrade path from PyTorch 2.6 to 2.8+ for native RTX 5070 Ti (sm_120) support in the TRIBE v2 scorer.

## 1. Current State

| Component       | Version / Value                          |
|-----------------|------------------------------------------|
| PyTorch         | 2.5.1-2.6.x (`torch>=2.5.1,<2.7`)      |
| CUDA Toolkit    | 12.6                                     |
| Python          | 3.11 (required by pyannote.audio)        |
| GPU             | NVIDIA RTX 5070 Ti (12.2 GB VRAM)       |
| Architecture    | Blackwell (compute capability sm_120)    |
| sm_120 Support  | JIT fallback compilation only            |

PyTorch 2.6 does not include precompiled kernels for sm_120. The GPU still works because PyTorch falls back to just-in-time (JIT) PTX compilation at runtime. This adds overhead to first-run inference and uses slightly more VRAM than native kernels would.

## 2. Why We're Pinned

The `torch>=2.5.1,<2.7` pin in `tribe_scorer/requirements.txt` exists because of a chain of downstream dependencies:

1. **pyannote.audio** -- The audio diarization library used by WhisperX. It pins specific PyTorch version ranges and is typically slow to release updates for new PyTorch majors. This is the primary blocking dependency.
2. **WhisperX** -- Depends on pyannote.audio for speaker diarization. Cannot upgrade torch independently of pyannote.
3. **torchvision / torchaudio** -- Must match the torch major version exactly. Upgrading torch requires upgrading both in lockstep.
4. **TRIBE v2 vendor code** -- Uses neuralset and other torch-dependent code that has been tested against PyTorch 2.6. Located in `tribe_scorer/vendor/tribev2/` (Git submodule).
5. **Python 3.11 constraint** -- pyannote.audio requires Python 3.11. This limits which PyTorch wheels are available (some nightly builds skip 3.11).

## 3. Target State

| Component       | Target Value                             |
|-----------------|------------------------------------------|
| PyTorch         | 2.8.x+ (first stable with sm_120)       |
| CUDA Toolkit    | 12.6+ (keep current or upgrade to 12.8) |
| Python          | 3.11 (unchanged unless pyannote drops it)|
| sm_120 Support  | Native precompiled kernels               |

## 4. Expected Improvements

### Performance
- **Faster first inference**: No JIT PTX compilation on first run. Currently, the first TRIBE v2 score request after startup incurs extra latency while CUDA JIT-compiles kernels for sm_120. Native support eliminates this.
- **Lower VRAM overhead**: Native kernels are optimized for the target architecture. JIT-compiled kernels may use suboptimal register allocation.
- **Better throughput**: Precompiled kernels can leverage sm_120-specific features (potentially improved tensor core scheduling, memory coalescing patterns).

### Stability
- **Reduced JIT cache issues**: The exca cache + CUDA JIT cache interaction on Windows has caused MAX_PATH issues. Native kernels reduce reliance on the JIT cache.
- **Better CUDA 12.x integration**: PyTorch 2.8 will have more mature CUDA 12.6+ support, reducing edge cases.

### Quantified estimate
Expect 5-15% inference speedup and 100-300 MB VRAM reduction per model load. Actual numbers depend on PyTorch 2.8 kernel optimizations and must be benchmarked (see step 5f below).

## 5. Step-by-Step Upgrade Procedure

Complete these steps in order. Do not skip the compatibility checks -- a broken pyannote.audio install will silently produce incorrect diarization results.

### a. Check pyannote.audio compatibility with PyTorch 2.8

```bash
# Check pyannote.audio's published compatibility
pip index versions pyannote.audio
# Review the pyannote.audio changelog and GitHub issues for PyTorch 2.8 support
# URL: https://github.com/pyannote/pyannote-audio/releases
```

Look for:
- An explicit mention of PyTorch 2.8 in release notes
- Updated `install_requires` in their `setup.cfg` / `pyproject.toml`
- No open issues tagged "pytorch 2.8" reporting breakage

**Do not proceed if pyannote.audio has not confirmed 2.8 compatibility.**

### b. Check WhisperX compatibility

```bash
# Check WhisperX requirements
pip show whisperx | grep -i requires
# Review WhisperX GitHub for PyTorch 2.8 support
# URL: https://github.com/m-bain/whisperX/issues
```

WhisperX must work with both the new torch version and the new pyannote.audio version.

### c. Update requirements.txt pins

In `tribe_scorer/requirements.txt`, change:
```
torch>=2.5.1,<2.7
```
to:
```
torch>=2.8.0,<2.9
```

Also verify that `torchvision` and `torchaudio` versions are compatible (they are installed separately via the pip index URL, not pinned in requirements.txt).

### d. Test in isolated venv

```bash
# Create a fresh test venv (do NOT modify the production .venv yet)
cd tribe_scorer
python3.11 -m venv .venv-test
source .venv-test/bin/activate

# Install PyTorch 2.8 with CUDA 12.6
pip install torch==2.8.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Install TRIBE v2 vendor code
pip install -e ./vendor/tribev2

# Install remaining scorer dependencies
pip install -r requirements.txt

# Verify torch sees the GPU and reports correct compute capability
python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
cap = torch.cuda.get_device_capability(0)
print(f'Compute capability: sm_{cap[0]}{cap[1]}0')
print(f'CUDA version: {torch.version.cuda}')
"
```

Expected output should show `Compute capability: sm_120`.

### e. Run full TRIBE v2 test suite

```bash
# From project root, with test venv active
python -m tribe_scorer.main &
SCORER_PID=$!
sleep 60  # Wait for model load

# Health check
curl -s http://localhost:8001/health | python -m json.tool

# Run a test score request
curl -s -X POST http://localhost:8001/score \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test sentence for TRIBE v2 scoring."}' | python -m json.tool

kill $SCORER_PID
```

Verify:
- Health endpoint returns `{"status": "ok"}`
- Score response contains all 7 neural dimensions with numeric values
- No CUDA errors in scorer logs

### f. Benchmark inference time and VRAM usage before/after

Run this benchmark **before** upgrading the production venv, then again **after**:

```bash
# Record baseline (current PyTorch 2.6)
python -c "
import torch
import time

# Log VRAM before model load
print(f'VRAM allocated (pre-load): {torch.cuda.memory_allocated() / 1024**2:.1f} MB')

# The actual benchmark should score 10 identical texts and average the time
# Use the TRIBE v2 scorer HTTP API for realistic end-to-end timing
"

# Use curl with timing for end-to-end measurement
for i in {1..10}; do
  curl -s -o /dev/null -w "%{time_total}\n" \
    -X POST http://localhost:8001/score \
    -H "Content-Type: application/json" \
    -d '{"text": "Benchmark test sentence for measuring inference performance."}'
done
```

Record: average inference time, peak VRAM usage, first-run vs. warm-run difference.

## 6. Upgrade Command Sequence

Once all checks in section 5 pass, apply to the production venv:

```bash
# In tribe_scorer/.venv
source tribe_scorer/.venv/bin/activate

# Upgrade PyTorch and companions
pip install torch==2.8.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Reinstall TRIBE v2 vendor code against new torch
pip install -e ./vendor/tribev2

# Reinstall remaining deps to ensure compatibility
pip install -r tribe_scorer/requirements.txt

# Verify installation
python -c "import torch; print(torch.__version__, torch.cuda.get_device_capability(0))"

# Start the scorer and run a smoke test
python -m tribe_scorer.main
```

## 7. Rollback Instructions

If the upgrade causes issues, restore PyTorch 2.6:

```bash
source tribe_scorer/.venv/bin/activate

# Reinstall PyTorch 2.6 with CUDA 12.4 index (2.6 was built against 12.4)
pip install "torch>=2.5.1,<2.7" torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Reinstall TRIBE v2 vendor code against restored torch
pip install -e ./vendor/tribev2

# Verify rollback
python -c "import torch; print(torch.__version__, torch.cuda.get_device_capability(0))"

# Restart scorer
python -m tribe_scorer.main
```

Also revert `tribe_scorer/requirements.txt` to the `<2.7` pin:
```
torch>=2.5.1,<2.7
```

## 8. Decision Criteria

Pull the trigger on the upgrade when ALL of these are true:

- [ ] PyTorch 2.8 has a stable release (not RC or nightly)
- [ ] pyannote.audio has a release explicitly supporting PyTorch 2.8
- [ ] WhisperX works with the new pyannote.audio + PyTorch 2.8 combination
- [ ] Python 3.11 wheels are available for torch 2.8 on the cu126 index
- [ ] The isolated venv test (step 5d) passes cleanly
- [ ] TRIBE v2 scorer produces identical scores (within floating-point tolerance) on the same input text
- [ ] Benchmark shows no performance regression

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| pyannote.audio lags behind PyTorch releases | High | Blocks upgrade entirely | Monitor pyannote GitHub; consider pinning an older pyannote if a compatible version exists |
| WhisperX lags behind pyannote.audio updates | Medium | Blocks upgrade | WhisperX has historically followed pyannote within 1-2 months |
| TRIBE v2 vendor code uses deprecated torch APIs | Low | Requires vendor code patches | Submodule is vendored; we can patch locally if needed |
| Score drift (different results on same input) | Low | May invalidate prior campaign results | Compare scores on a reference corpus before and after; accept if delta < 0.01 |
| Python 3.11 dropped by PyTorch 2.8 | Low | Requires Python upgrade, which may break pyannote | Check wheel availability early; Python 3.11 is still in active support |
| CUDA 12.6 not supported by PyTorch 2.8 wheels | Low | Must upgrade CUDA toolkit | PyTorch typically supports multiple CUDA versions; check index URL availability |

## 10. Monitoring

After upgrading, verify that sm_120 native support is active:

```python
import torch

# Check compute capability
major, minor = torch.cuda.get_device_capability(0)
print(f"Compute capability: sm_{major}{minor}0")
assert (major, minor) == (12, 0), f"Expected sm_120, got sm_{major}{minor}0"

# Check that CUDA is using native kernels (no JIT fallback)
# If native support is active, there should be no PTX JIT compilation messages
# in the CUDA log output. Set CUDA_LAUNCH_BLOCKING=1 for verbose output.
print(f"PyTorch CUDA arch list: {torch.cuda.get_arch_list()}")
# Should include 'sm_120' in the arch list with native support
```

Run this check:
```bash
# Quick verification script
python -c "
import torch
cap = torch.cuda.get_device_capability(0)
arch_list = torch.cuda.get_arch_list()
print(f'Device: {torch.cuda.get_device_name(0)}')
print(f'Compute capability: sm_{cap[0]}{cap[1]}0')
print(f'Supported architectures: {arch_list}')
if 'sm_120' in arch_list:
    print('STATUS: Native sm_120 support is ACTIVE')
else:
    print('STATUS: Using JIT fallback (sm_120 not in arch list)')
"
```

When native support is active:
- `torch.cuda.get_device_capability(0)` returns `(12, 0)`
- `torch.cuda.get_arch_list()` includes `'sm_120'`
- No `ptxas` JIT compilation warnings appear in scorer startup logs
- First inference is noticeably faster than with JIT fallback

---

*Last updated: 2026-04-13. Revisit when PyTorch 2.8 stable is released.*
