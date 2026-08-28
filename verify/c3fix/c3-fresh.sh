#!/usr/bin/env bash
# Reps 2..N of the corrected C3 comparison, FRESH CONTEXT ONLY (-d 0).
#
# Why this exists: the -d 4096 half costs ~10 min per Vulkan cell (Vulkan degrades
# badly at depth) versus ~2.6 min for HIP, which put the full 4-rep matrix ~1.5h out.
# Rep 1 already carries the complete both-depths measurement, so depth coverage is
# preserved at n=1; these reps add statistical power where the HIP-vs-Vulkan ratio is
# actually contested -- fresh-context prefill and generation.
#
# Same anti-confound design as c3-fix.sh: nothing samples anything during a timed run,
# the backends are interleaved within each rep, and the leading backend alternates so
# thermal/clock drift cannot systematically favour one arm. Appends to the same CSV.
set -uo pipefail

ROOT=/mnt/d/AI_Projects/llama-cpp-amd
OUT="$ROOT/verify/c3fix"
CSV="$OUT/results.csv"
MODEL='D:\AI_Projects\models\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf'
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
REP_START="${REP_START:-2}"
REP_END="${REP_END:-4}"
NCMOE_LIST="${NCMOE_LIST:-28 32}"

run_one() {          # backend ncmoe rep
  local be=$1 nc=$2 rep=$3
  local exe="D:\\AI_Projects\\llama-cpp-amd\\$be\\llama-bench.exe"
  local log="$OUT/${be}_nc${nc}_r${rep}_fresh.log"
  local t0 t1
  t0=$(date +%s.%N)
  "$PS" -NoProfile -Command \
    "& '$exe' -m '$MODEL' -ngl 99 -ncmoe $nc -p 512 -n 128 -d 0 -r 3 -o md" \
    > "$log" 2>&1
  t1=$(date +%s.%N)
  local wall; wall=$(echo "$t1 - $t0" | bc)

  local dec="$log.txt"
  iconv -f UTF-16LE -t UTF-8 "$log" 2>/dev/null | grep -q '|' && \
    iconv -f UTF-16LE -t UTF-8 "$log" > "$dec" || cp "$log" "$dec"

  awk -v rep="$rep" -v be="$be" -v nc="$nc" -v wall="$wall" -F'|' '
    /qwen3moe/ {
      test=$8; val=$9
      gsub(/^[ \t]+|[ \t]+$/,"",test); gsub(/^[ \t]+|[ \t]+$/,"",val)
      n=split(val,a,/[ \t]+/); tps=a[1]; sd=(n>=3?a[3]:"")
      if (test != "" && tps ~ /^[0-9.]+$/)
        printf "%s,%s,%s,%s,%s,%s,%.1f\n", rep, be, nc, test, tps, sd, wall
    }' "$dec" >> "$CSV"
}

for rep in $(seq "$REP_START" "$REP_END"); do
  for nc in $NCMOE_LIST; do
    if [ $((rep % 2)) -eq 1 ]; then order="hip-gfx1010 vulkan"; else order="vulkan hip-gfx1010"; fi
    for be in $order; do
      echo "== rep $rep | $be | -ncmoe $nc | fresh-only =="
      run_one "$be" "$nc" "$rep"
      tail -2 "$CSV"
    done
  done
done
echo "== fresh-only reps $REP_START..$REP_END done -> $CSV =="
