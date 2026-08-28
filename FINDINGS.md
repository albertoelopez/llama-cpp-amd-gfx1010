# AMD RX 5700 XT — HIP/ROCm + VRAM+RAM MoE offload: verified findings

Durable copy of the findings section of FreeToken's NEXT.md. Kept here because a
session-checkpoint hook used to overwrite that file (fixed 2026-08-27 to append below
a marker, but this directory is not a git repo, so it stays the backup of record).

Copied 2026-08-27 22:05 PDT

---

# Goal: VRAM + RAM MoE offload on AMD (like FreeToken does on NVIDIA)

Findings below are hand-written — do not let the checkpoint hook clobber them. (It clobbered
them once already, 2026-08-27: this file was found reduced to the bare stub above and had to be
restored from a dangling git commit, `349ddbd`, recovered via `git fsck --dangling`. If you are
a checkpoint hook: **append below this line, never replace it.**)

## Outcome: working on BOTH backends; HIP is faster at most settings, NOT a blanket "~2x"

**CORRECTED 2026-08-27.** Independent re-measurement found the original "~2x" headline and the
single-run numbers immediately below were both wrong in different ways. Read "Performance is
not a point value" and "HIP vs Vulkan — how much faster, really" before quoting anything here
as a stable fact.

Runs a **17.28 GB / 30B-param MoE model on an 8 GB RX 5700 XT**. Best setting found so far:

```powershell
D:\AI_Projects\llama-cpp-amd\hip-gfx1010\llama-cli.exe `
  -m D:\AI_Projects\models\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf `
  -ngl 99 -ncmoe 28
```

~~HIP @ `-ncmoe 28`: **~144 t/s prefill / ~19.5 t/s gen** fresh, **~63 / ~14** at 4096-deep.
Vulkan fallback (`vulkan\llama-cli.exe -ngl 99 -ncmoe 32`): ~70 / ~11 fresh, ~42 / ~12 deep.~~
**UNRELIABLE as stated — those were single point-in-time runs, not stable figures.** See below.

Model is 48 layers / 128 experts per layer / top-8 routed. `-ncmoe N` = how many
layers' experts compute on CPU; range 0–48. Hardware: Ryzen 5 3600 (6C/12T),
RX 5700 XT with ~7.3 GiB free VRAM.

## Performance is not a point value — VERIFIED 2026-08-27

Independent re-measurement of the exact "best setting" above (HIP `-ncmoe 28`) produced pp512
figures of **40.08 (cold), 91.00, 105.83, 128.41, 133.83 ± 16.74, and 107.41 ± 10.43 t/s**
across separate runs of the *same* config — not one stable number. Back-to-back **identical
warm** runs varied by roughly **25%** on HIP, while Vulkan at the same setting was stable to
**~4%**. No GPU clock/power/thermal telemetry was available to explain the swing (the Windows
HIP SDK 6.2 ships no `rocm-smi`), so the instability itself is unexplained, not just unlucky
sampling.

**Practical consequence: quote a range, not a figure**, for HIP `-ncmoe 28` prefill — roughly
**40–170 t/s** depending on run, no single "the" number. Do not repeat "144 t/s" as if it were
reproducible.

A corrected, methodologically-clean re-measurement (interleaved HIP/Vulkan reps so thermal/clock
drift hits both arms equally, no perf-counter sampling during timed runs, both `-ncmoe 28` and
`32` measured since the backends cross over between them — see "Measurement pitfalls" below) is
running now and will land in `/mnt/d/AI_Projects/llama-cpp-amd/verify/c3fix/results.csv`. Treat
that path as the forthcoming authoritative source; the numbers in this file are the best
evidence *as of this checkpoint*, not final — re-read and update once it lands.

## HIP vs Vulkan — SETTLED 2026-08-27 by a clean re-measurement (supersedes everything above)

Data: `D:\AI_Projects\llama-cpp-amd\verify\c3fix\results.csv` (28 rows). Protocol:
`c3-fix.sh` (rep 1, both depths, both `-ncmoe`) + `c3-fresh.sh` (reps 2-4, fresh, `-ncmoe 28`),
analysed by `analyze.py`. No sampling during timed runs; backends interleaved WITHIN each rep
with the leading backend alternating, so drift affecting both arms cancels in the paired ratio.

### Headline: at `-ncmoe 28` fresh context there is NO RELIABLE WINNER.

Paired HIP/Vulkan pp512 ratio over 4 reps: **1.68, 1.33, 0.57, 0.94** (median 1.14) — it
straddles 1.0. Generation likewise: 1.09, 1.20, 0.52, 1.02 (median 0.97). Whichever backend
"wins" depends on which draw you take. This is why every earlier attempt disagreed.

### The stable finding is VARIANCE, not speed.

| backend | pp512 range over 4 identical runs | spread |
|---|---|---|
| HIP    | 44.31 – 144.87 t/s | **150%** |
| Vulkan | 47.77 –  85.99 t/s | 50% |

HIP's throughput varies ~3x run-to-run on identical config; Vulkan is far more predictable
(its tight cells reach ±0.75). Cause still UNKNOWN — a thermal-drift hypothesis was
FALSIFIED when Vulkan recovered (85.99 -> 47.77 -> 78.37 -> 74.41) while HIP kept sliding in
the same interleaved sequence. No `rocm-smi` on the Windows HIP SDK 6.2, so clocks/power/temps
remain unobservable. Treat any single HIP benchmark on this card as near-uninformative.

### Where clear differences DO exist (n=1 — directional, not established)

- `-ncmoe 28` @ depth 4096: **HIP 19.6x** (60.46 vs 3.09 t/s). Vulkan collapses; ~20 GPU-resident
  expert layers + a 4096-token KV cache exceed the 8 GiB card and WDDM spills. Vulkan's cell took
  1181 s vs HIP's 154 s — the wall clock corroborates the throughput independently.
- `-ncmoe 32` fresh: **Vulkan 3.6x** (154.97 vs 43.15). No VRAM pressure at 16 resident layers.
- `-ncmoe 32` @ depth: near parity (HIP 1.19x prefill, 1.03x generation).

### Practical guidance
Choose by VRAM headroom at your working context length, NOT by a throughput ratio. For
long-context chat, `-ncmoe 28` on HIP is the pick — the one place a large, robust gap exists.
For short prompts either backend is fine and Vulkan is the more predictable of the two.

### Superseded claims (do not carry forward)
- "~2x HIP" (this file, earlier) — unsupported at fresh context.
- "the backends are within 0.8%" (`verify/summary.txt`) — artifact of that harness's own
  perf-counter sampling; see "Measurement pitfalls".
- "HIP ~1.43x Vulkan" — too confident; the real per-rep ratios straddle 1.0.
- "143.76 t/s is unreachable" — it IS reproducible (144.87 in rep 1), but only as the TOP of a
  44–145 t/s range, never as a typical value.

## ROCm/HIP on this card — CORRECTED (2026-08-25 late session; root cause tightened 2026-08-27)

Earlier conclusion "ROCm can't see the RX 5700 XT" was WRONG. Verified with a ctypes probe
(`D:\AI_Projects\llama-cpp-amd\hip_probe.py`, `hip_arch_probe.py`): the driver's own HIP
runtime (`C:\Windows\System32\amdhip64_6.dll`, HIP 6.2.4) enumerates the card as
**`gfx1010:xnack-`**, 7.98 GiB. AMD's official table marks RDNA1 ❌ but that is a support
statement, not a technical limit.

**VERIFIED root cause of the prebuilt build's "zero devices":** a **runtime-version
mismatch**, not missing gfx1010 kernels. `D:\AI_Projects\llama-cpp-amd\rocm\ggml-hip.dll`
imports `amdhip64_7.dll` (ROCm/HIP 7), but this machine's driver only ships the ROCm 6 runtime
(`amdhip64_6.dll`, HIP 6.2.4) — the import fails to resolve, so ggml's backend loader silently
skips that DLL and llama.cpp reports "(none)". `hip-gfx1010\ggml-hip.dll` (the working custom
build) imports `amdhip64_6.dll` instead, which is why it loads. The prebuilt DLL's code-object
targets (gfx1011/1012, gfx103x, gfx11xx, gfx12xx — no gfx1010) are a real, separate gap, but
they are **not** what produces "zero devices": the process never gets far enough to enumerate
targets, because the DLL itself never loads.

WSL2 ROCm is genuinely out (AMD: RX 7000/9000 only). Native Windows HIP is the path.

### What was done (all under `D:\AI_Projects\llama-cpp-amd\`)
- **AMD HIP SDK 6.2.4 installed** (`AMD-Software-PRO-Edition-24.Q4-Win10-Win11-For-HIP.exe`,
  sha256 `5aa79815e5e8…d24e67`, AMD-signed) -> `C:\Program Files\AMD\ROCm\6.2`, `HIP_PATH` set.
  **WARNING: silent `-install` REPLACED the display driver** despite AMD docs saying it
  wouldn't: Adrenalin 24.12.1 (32.0.12033.1030) -> PRO Edition 24.Q4 (32.0.12052.2, Jan 2025).
  Driver is healthy and newer; reinstall Adrenalin from AMD if gaming features are missed.
- **Community rocBLAS with gfx1010:xnack- Tensile kernels swapped in** (likelovewant ROCmLibs
  v0.6.2.4, asset `rocm.gfx1010-xnack-gfx1011-xnack-gfx1012-xnack-.for.hip.sdk.6.2.4.7z`).
  Stock kept as `rocblas.dll.orig` / `rocblas\library.orig`. Script: `swap-rocblas-gfx1010.ps1`.
  The xnack- variant is required because that is the exact arch string the runtime reports.
  **VERIFIED 2026-08-27 — this swap is NOT load-bearing for the measured inference path.**
  Read "rocBLAS swap — verified not load-bearing" below before assuming it's necessary.
- llama.cpp **b10630** (same commit as the Vulkan binaries) cloned to `src\`.
- Build script `build-hip-gfx1010.ps1`: `-DGGML_HIP=ON -DGPU_TARGETS=gfx1010`, SDK clang,
  Ninja (bundled in VS 2022 Build Tools), output -> `hip-gfx1010\` (self-contained with
  hipblas/rocblas DLLs + `rocblas\library`). Log: `build_hip.log` (UTF-16LE).
- Toolchain present: CMake 4.1 (`D:\Programs\CMake`), VS 2022 Build Tools (MSVC 14.44), Win SDK.

## rocBLAS swap — verified NOT load-bearing for the measured Q4_K_M inference path (2026-08-27)

Captured the AMD runtime's full kernel-dispatch history for two representative workloads: a
generation-heavy run (**7,807 dispatches, 23 distinct kernels**) and a pure-prefill `pp512`
run. **Zero rocBLAS/Tensile dispatches in either.** Every matmul goes through ggml's own MMQ
kernels (`mul_mat_q`, `mul_mat_vec_q`, `quantize_mmq_q8_1`); `rocblas.dll` loads only as a
link-time dependency of the build — it is never actually invoked for this quant type.

**Do not overstate this as "the swap was unnecessary."** What was and wasn't tested:
- NOT tested: whether the build would even link/load against AMD's *stock* rocBLAS (no
  gfx1010:xnack- Tensile kernels) instead of the community one.
- NOT tested: whether other quant types (non-Q4_K_M) route through rocBLAS/hipBLAS and would
  need the community kernels.

Correct framing: **the swap is not load-bearing for the measured Q4_K_M inference path;
whether the stock rocBLAS would suffice was not tested.** Keep doing the swap until that's
checked — don't strip it out on the strength of this finding alone.

### RESULT: HIP build WORKS on the RX 5700 XT
- `hip-gfx1010\llama-cli.exe --list-devices` -> `ROCm0: AMD Radeon RX 5700 XT (8176 MiB)`.
- Smoke test (Qwen2.5-3B Q4_K_M, `-ngl 99`): correct output, no rocBLAS/Tensile errors,
  Prompt 252 t/s / Generation 48.9 t/s. (Vulkan on the same prompt: 252 / 89.3.)
- Global `~/.claude/CLAUDE.md` updated accordingly.
- MoE `-ncmoe` sweep on HIP (`hip_sweep.log`, `hip_sweep2.log`; same shape as the Vulkan
  run: `-p 512 -n 256 -d 0,4096 -r 3`, 2026-08-26). **These are single historical runs — see
  "Performance is not a point value" above; treat as illustrative of shape across `-ncmoe`,
  not as reproducible figures:**

  | `-ncmoe` | GPU-resident expert layers | pp512 | tg256 | pp512 @ d4096 | tg256 @ d4096 |
  |---|---|---|---|---|---|
  | 24 | 24 | **OOM at model load** | | | |
  | **28** | 20 | **143.76 ± 10.21** | **19.45 ± 0.32** | **62.63 ± 0.08** | **14.04 ± 0.45** |
  | 32 | 16 | 37.11 ± 15.49 (*) | 11.47 ± 1.81 (*) | 54.78 ± 2.57 | 13.01 ± 0.08 |
  | 36 | 12 | 129.70 ± 36.55 | 16.18 ± 0.87 | 62.59 ± 3.60 | 13.95 ± 0.37 |
  | 40 | 8 | 129.33 ± 6.87 | 14.00 ± 1.17 | 63.05 ± 0.83 | 12.46 ± 0.22 |
  | 48 | 0 | 109.58 ± 8.67 | 12.96 ± 0.15 | 60.60 ± 1.47 | 10.77 ± 0.27 |

  (*) the `32` fresh-context row was the first MoE load after the build (cold page cache on
  the 18 GB file) and is inconsistent with its neighbours; its deep-context numbers are fine.
  Treat it as an artifact, not a real dip. Re-measure if it matters.

  **Recommendation: `-ngl 99 -ncmoe 28`** — best on every column in *this* sweep, tight
  variance in *this* sweep, and it is the most GPU-resident split that fits. The old claim
  here ("~2x prefill / ~1.75x generation vs Vulkan's best") is **removed as unreliable** — see
  "HIP vs Vulkan — how much faster, really" above for the corrected, matched-setting
  comparison, and note the backends cross over at `-ncmoe 32`.

  **Why `-ncmoe 24` OOMs on HIP but "worked" on Vulkan:** each MoE layer's experts are
  128 x 3 x 2048 x 768 ≈ 604M params ≈ 340 MB at Q4_K_M. 24 GPU-resident layers ≈ 8.2 GB of
  experts alone > 8 GB VRAM. Vulkan/WDDM silently spilled to system RAM over PCIe (hence its
  flat, noisy numbers at ncmoe ≤ 24); HIP's `hipMalloc` fails honestly. HIP has no
  oversubscription safety net — pick a split that genuinely fits.

  Even all-CPU experts (`48`) on HIP (109.6 / 13.0) beats Vulkan's best from this same sweep —
  i.e. HIP's attention/KV kernels alone are a meaningful part of whatever edge HIP has — but
  see "HIP vs Vulkan — how much faster, really" above for how much that edge actually is under
  a clean, matched comparison.

  **Measured VRAM/RAM placement at `-ncmoe 28`** (llama.cpp's own loader + exit-time
  `memory breakdown`, `place28.log`, n_ctx 4096):
  ```
  CPU_Mapped model buffer size = 10197.74 MiB   (system RAM: experts of 28 layers)
       ROCm0 model buffer size =  7808.92 MiB   (VRAM: attention + experts of 20 layers)
       ROCm0 KV buffer size    =   384.00 MiB   (VRAM)
       ROCm0 compute buffer    =   221.51 MiB   (VRAM)
  ROCm0: 8176 = 0 free + (8414 = 7808 + 384 + 221) + unaccounted -238
  ```
  i.e. the split is real and ~238 MiB OVER the 8176 MiB card at 4k ctx — Windows HIP
  tolerates a small spill to shared memory (Task Manager "shared" ≈ 2 GB for the process),
  it only refuses when one allocation can't fit at all (`-ncmoe 24`). So the earlier "no
  safety net" note is too strong: small spills OK, big ones fail at load. Windows counters
  mid-generation agreed: 7,276 MiB VRAM dedicated + 2,092 MiB shared, 15.0 GB working set.
  Practical consequence: at `-ncmoe 28` keep `-c` modest (each 4k of ctx ≈ +384 MiB VRAM);
  `llama-cli` defaults to the model's n_ctx_train (262144!) — ALWAYS pass `-c`.
  Verified `-c 8192` at `-ncmoe 28` (`place28b.log`): KV 768 MiB, ROCm0 8802 requested vs
  8176 (unaccounted -626, i.e. ~626 MiB spilled) and it still ran fine — 16.7 t/s gen /
  14.0 t/s prompt on a warm cache, 154 tokens, exit 0. So 8k ctx is a safe ceiling at 28;
  beyond that either drop to `-ncmoe 32` (frees ~1.4 GB) or expect the spill to bite.

### Build gotchas hit on the way (all fixed in the scripts)
- PowerShell 5 + `$ErrorActionPreference = "Stop"` aborts on CMake's harmless stderr line
  (`CMAKE_BUILD_TYPE=Release`) -> use "Continue" and check `$LASTEXITCODE`.
- `hip-config.cmake` runs `hipconfig`, which is a **Perl** script on the Windows SDK. No
  perl on PATH -> "Unexpected HIP_PLATFORM:". Fix: `-DHIP_PLATFORM=amd` (skips hipconfig)
  and append Git's `C:\Program Files\Git\usr\bin` to PATH — append LAST, it has a GNU
  `link.exe` that would shadow MSVC's.
- llama.cpp b10630 `ggml/src/ggml-cuda/vendors/hip.h` does
  `typedef __hip_fp8_e4m3 __nv_fp8_e4m3;` under `HIP_VERSION >= 60200000`, but HIP SDK
  6.2.4 only ships `__hip_fp8_e4m3_fnuz`. Patched the typedef to `HIP_VERSION >= 60300000`
  (the alias is only used by CUDA/Blackwell-only branches). Local, uncommitted edit in `src\`.
- Build: 514 steps, ~15 min on the Ryzen 3600. Output dir is self-contained
  (hipblas/rocblas DLLs + `rocblas\library` copied in).

## Correctness — verified with a caveat (2026-08-27)

`test-backend-ops` shows **36 bf16 / hsk=64 `FLASH_ATTN_EXT` cases failing** against the CPU
reference on gfx1010. **The models actually in use here do not enter that path** (this Qwen3
MoE run never hits bf16 hsk=64 flash-attn), so this is a caveat, not a blocker for current use
— but it means gfx1010 kernel correctness is spot-checked, not blanket-verified.

End-to-end correctness was separately checked with `llama-perplexity` over 4096 tokens:
**GPU PPL 8.6288 vs CPU 8.6724** (-0.50% relative), with the **GPU lower in 8 of 8 chunks** —
small, but systematically one-sided rather than symmetric noise. Worth watching if it matters
for a given use case; not large enough to be alarming for chat/instruct use, but don't claim
"numerically identical to CPU" — it isn't, quite.

## Measurement pitfalls — the single most useful lesson here (2026-08-27)

An earlier report concluded HIP and Vulkan were "within 0.8%" of each other at matched
`-ncmoe 28`. **That conclusion was itself an artifact of its own measurement harness**, which
polled Windows perf counters (`Get-Counter`/`typeperf`) throughout every timed run. On a
6-core CPU already busy running 28 layers of MoE experts on the CPU side, that sampler stole
enough CPU from the expert layers to suppress HIP prefill by **~21%**, while barely touching
Vulkan — producing a confident, wrong "the backends are equal" result. Do not trust or repeat
that "within 0.8%" figure; see "HIP vs Vulkan — how much faster, really" above for the
corrected comparison.

**Rule going forward: never sample perf counters (or anything else) during a timed run on
this box. Measure OR instrument, never both in the same run.** This is now enforced by a
`PreToolUse` hook (`.claude/hooks/gpu-exclusive.sh`) that refuses to launch a benchmark binary
in the same command as a perf-counter sampler, and refuses to launch a second GPU job while
one is already running (a second silent-failure mode: two llama.cpp processes on one 8 GiB
card contend for VRAM/compute and can OOM at load).

## Benchmark data (`llama-bench`, build b10630-d222767c7)

Short burst (`-p 128 -n 64 -r 3`) — **misleading, see below**:

| `-ncmoe` | pp128 t/s | tg64 t/s |
|---|---|---|
| 48 (all CPU) | 17.33 ± 5.02 | 9.42 ± 1.79 |
| 40 | 29.44 | 14.60 |
| 32 | 33.80 | 16.67 |
| 24 | 39.94 | 17.37 |
| 16 | 39.69 | 13.52 |
| 8 | 19.93 ± 12.00 (unstable) | 10.73 |
| 0 | **77.81** | **19.79** |

Realistic load (`-p 512 -n 256 -d 0,4096 -r 3`):

| `-ncmoe` | pp512 | tg256 | pp512 @ d4096 | tg256 @ d4096 |
|---|---|---|---|---|
| 32 | 70.12 ± 16.66 | 11.03 | 41.68 | 11.76 |
| 24 | 34.39 | 10.79 | 33.83 ± 1.27 | 11.51 ± 0.16 |
| 16 | 41.69 | 12.81 | 34.98 | 10.30 |

## Traps / lessons

- **`-ncmoe 0` is a trap.** Fastest in short bursts, but **OOMs at model load** on any
  realistic context: `ggml_vulkan: Device memory allocation of size 972343296 failed`
  → `ErrorOutOfDeviceMemory`. The short-burst win was an artifact of a tiny KV cache.
- **Short benchmarks mislead.** `-p128 -n64` suggested `ncmoe=24` beat `ncmoe=16` by
  ~28%; under real load they are within noise. Tune against realistic shapes.
- **Even "realistic shape" HIP numbers are not a stable point value** — see "Performance is
  not a point value" above; a warm, realistic-shape `-ncmoe 28` run still varies ~25%
  run-to-run on this card.
- `-ncmoe 8` shows huge variance (±12 on prefill) — VRAM/shared-memory thrash zone, avoid.
- First-ever baseline run (5.24 / 2.71 t/s) was cold-page-cache noise on an 18 GB file,
  not a real config result.
- `llama-cli` timing line (e.g. `Generation: 4.8 t/s`) includes cold model load — not
  comparable to `llama-bench` steady-state numbers. Trust `llama-bench`.
- `llama-cli` flags in this build: `-st` / `--single-turn` (NOT `-no-cnv`), `--simple-io`.
- Logs are UTF-16LE: decode with `iconv -f UTF-16LE -t UTF-8 <file>`.
- `llama-bench.exe` runs long; poll for the process to exit rather than trusting the
  launcher's exit (`Get-Process llama-bench`).
- **Never sample perf counters during a timed run** — see "Measurement pitfalls" above.

## Mechanism caveat

llama.cpp `-ncmoe` is a **static per-layer** CPU/GPU split decided at load. FreeToken's
approach is different and finer-grained: experts pinned in host RAM + a **GPU-side LRU
expert cache**, per-token PCIe streaming of misses only, with a bandwidth-adaptive
CPU/PCIe split (`ft bench bw`, q* policy). Same goal, coarser mechanism; FreeToken's
would likely do better, but porting it to HIP is not worth it for a GPU outside ROCm's
support matrix.

## Unrelated but open

- Defender quarantined 4 binaries in `D:\AI_Projects\llama-cpp-amd\rocm\` as
  `Trojan:Win32/Wacatac.B!ml` / `.C!ml` (severity: Severe): `llama-batched.exe`,
  `llama-speculative-simple.exe`, `test-c.exe`, `test-recurrent-state-rollback.exe`.
  Almost certainly ML false positives on unsigned binaries; the ones we need survived.
  Those prebuilt binaries have no source tree / no origin recorded — provenance unknown.
- FreeToken Desktop installer (`D:\Downloads\FreeToken-Setup-win-x64.exe`) is unsigned
  NSIS, sha256 `326c29f20e0e8a2775fb02e19fde08015273d36d965ced536685fda20d0d5dfa`.
  It never appeared in Defender's history — not the source of the Trojan popup.
- `origin` is correctly `https://github.com/albertoelopez/FreeToken.git` (your fork).
  No `upstream` remote for `FlashML-org/FreeToken` — add one if you want their updates.
- Corrected HIP-vs-Vulkan re-measurement (`verify/c3fix/`) is running now; results will land
  in `verify/c3fix/results.csv`. Re-read this file and update the two sections above once it
  lands, rather than trusting the numbers currently written here as final.

Next session: read this file, then continue or run /ship.
