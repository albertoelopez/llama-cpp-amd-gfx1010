#!/usr/bin/env bash
# Corrected HIP-vs-Vulkan comparison (claim C3).
#
# Every design choice here answers a specific defect found in the previous attempts:
#
#  F1  A sampler polled perf counters during timed runs and suppressed HIP prefill
#      ~21%.                     -> nothing samples anything here. Timed runs are clean.
#  F6  An r1/r5 "load-cancelling" estimator assumed a constant per-repetition cost;
#      the runs' own timers showed it drifting 13%.
#                                -> no estimator. llama-bench's -r does the repetition,
#                                   and model load is excluded by a discarded warmup.
#  F7  Only fresh context was measured, yet the whole compound claim was ruled on.
#                                -> -d 0,4096 measures both halves.
#  F13 Back-to-back identical HIP runs varied 25% (Vulkan 4%), so any single number
#      is a draw from a wide distribution.
#                                -> REPS independent invocations per cell, and the
#                                   backends are INTERLEAVED so thermal/clock drift
#                                   hits both arms equally rather than whichever ran
#                                   second. Output is a distribution, not a point.
#
# Also: -ncmoe 28 and 32 are both measured because the two backends were observed to
# cross over between them (HIP ahead at 28, Vulkan ahead at 32) -- reporting either
# alone would misstate the result.
set -uo pipefail

ROOT=/mnt/d/AI_Projects/llama-cpp-amd
OUT="$ROOT/verify/c3fix"
CSV="$OUT/results.csv"
MODEL='D:\AI_Projects\models\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf'
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
REPS="${REPS:-4}"
NCMOE_LIST="${NCMOE_LIST:-28 32}"

mkdir -p "$OUT"
[ -f "$CSV" ] || echo "rep,backend,ncmoe,test,tps,stddev,wall_s" > "$CSV"

run_one() {          # backend ncmoe rep
  local be=$1 nc=$2 rep=$3
  local exe="D:\\AI_Projects\\llama-cpp-amd\\$be\\llama-bench.exe"
  local log="$OUT/${be}_nc${nc}_r${rep}.log"
  local t0 t1
  t0=$(date +%s.%N)
  "$PS" -NoProfile -Command \
    "& '$exe' -m '$MODEL' -ngl 99 -ncmoe $nc -p 512 -n 128 -d 0,4096 -r 3 -o md" \
    > "$log" 2>&1
  t1=$(date +%s.%N)
  local wall; wall=$(echo "$t1 - $t0" | bc)

  # llama-bench prints UTF-16LE through PowerShell redirection only when the shell
  # does the redirect; here bash owns the pipe, so the log is already UTF-8. Decode
  # defensively anyway -- a mis-decoded log silently yields zero rows.
  local dec="$log.txt"
  iconv -f UTF-16LE -t UTF-8 "$log" 2>/dev/null | grep -q '|' && \
    iconv -f UTF-16LE -t UTF-8 "$log" > "$dec" || cp "$log" "$dec"

  awk -v rep="$rep" -v be="$be" -v nc="$nc" -v wall="$wall" -F'|' '
    /qwen3moe/ {
      test=$8; val=$9
      gsub(/^[ \t]+|[ \t]+$/,"",test); gsub(/^[ \t]+|[ \t]+$/,"",val)
      # "133.83 ± 16.74" -- the separator is multi-byte, so split on whitespace.
      n=split(val,a,/[ \t]+/); tps=a[1]; sd=(n>=3?a[3]:"")
      if (test != "" && tps ~ /^[0-9.]+$/)
        printf "%s,%s,%s,%s,%s,%s,%.1f\n", rep, be, nc, test, tps, sd, wall
    }' "$dec" >> "$CSV"
}

echo "== warmup (discarded): pulls the 17.3 GiB model into page cache =="
run_one hip-gfx1010 28 0 >/dev/null 2>&1
grep -v '^0,' "$CSV" > "$CSV.tmp" && mv "$CSV.tmp" "$CSV"

for rep in $(seq 1 "$REPS"); do
  for nc in $NCMOE_LIST; do
    # Interleave the arms within each rep; alternate which goes first across reps so
    # neither backend permanently owns the cooler slot.
    if [ $((rep % 2)) -eq 1 ]; then order="hip-gfx1010 vulkan"; else order="vulkan hip-gfx1010"; fi
    for be in $order; do
      echo "== rep $rep | $be | -ncmoe $nc =="
      run_one "$be" "$nc" "$rep"
      tail -2 "$CSV"
    done
  done
done

echo "== done -> $CSV =="
column -s, -t < "$CSV"
