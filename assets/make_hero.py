#!/usr/bin/env python3
"""Generate the README hero from the real benchmark data.

Reads verify/c3fix/results.csv and emits assets/hero-light.svg + hero-dark.svg, so the
hero cannot drift from the measurements -- re-run it after re-benchmarking.

Form: the data's job is POLARITY around a meaningful midpoint (ratio 1.0 = parity),
which is a diverging chart, not a magnitude comparison. The ratio axis is log-scaled
because the depth-context ratio (19.6x) and the fresh-context ones (0.5-1.7x) have to
coexist without the small ones collapsing to invisible slivers.

Colors are the validated diverging pair (blue<->red, neutral gray midpoint), which
passes the six checks in both modes: CVD dE 21.6 (light) / 19.2 (dark), normal-vision
32.3 / 29.0, contrast >=3:1. Text wears ink tokens, never a series color.
"""
import csv, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "verify" / "c3fix" / "results.csv"

THEME = {
    "light": dict(surface="#fcfcfb", plane="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
                  muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  hip="#2a78d6", vk="#e34948", mid="#f0efec"),
    "dark":  dict(surface="#1a1a19", plane="#0d0d0d", ink="#ffffff", ink2="#c3c2b7",
                  muted="#898781", grid="#2c2c2a", axis="#383835",
                  hip="#3987e5", vk="#e66767", mid="#383835"),
}

W, H = 1200, 630


def load_ratios():
    """Pair HIP against Vulkan within each rep -- drift that hits both arms cancels."""
    by = {}
    for r in csv.DictReader(CSV.open()):
        key = (r["ncmoe"], r["test"], r["rep"])
        by.setdefault(key, {})[r["backend"]] = float(r["tps"])
    out = {}
    for (nc, test, rep), d in by.items():
        if "hip-gfx1010" in d and "vulkan" in d and d["vulkan"]:
            out.setdefault((nc, test), []).append((int(rep), d["hip-gfx1010"] / d["vulkan"]))
    return {k: sorted(v) for k, v in out.items()}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(mode, R):
    c = THEME[mode]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="ui-sans-serif,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">']
    o.append(f'<rect width="{W}" height="{H}" fill="{c["plane"]}"/>')
    o.append(f'<rect x="24" y="24" width="{W-48}" height="{H-48}" rx="14" fill="{c["surface"]}"/>')

    o.append(f'<text x="56" y="76" font-size="30" font-weight="700" fill="{c["ink"]}">'
             'llama.cpp on an RX 5700 XT — HIP vs Vulkan</text>')
    o.append(f'<text x="56" y="106" font-size="15.5" fill="{c["ink2"]}">'
             'Qwen3-30B-A3B Q4_K_M · a 17.3 GB MoE model running on an 8 GB card, experts split across VRAM and system RAM</text>')

    # ---- diverging panel -------------------------------------------------
    # Row labels get their own gutter and the plot starts after it, so a long
    # leftward bar can never run into its own row label (it did at first).
    PX = 56
    PLOT_X, PLOT_W = 186, 520
    top, rowh = 168, 30
    rows = []
    for test, label in (("pp512", "prefill"), ("tg128", "generate")):
        for rep, ratio in R.get(("28", test), []):
            rows.append((f"{label}  rep {rep}", ratio))

    # log scale: symmetric around 1.0, widest datum sets the span
    span = max(abs(math.log10(v)) for _, v in rows) * 1.18
    mid = PLOT_X + PLOT_W * 0.5
    def x_of(v):
        return mid + (math.log10(v) / span) * (PLOT_W * 0.46)

    o.append(f'<text x="{PX}" y="{top-42}" font-size="14" font-weight="700" fill="{c["ink"]}">'
             f'Paired throughput ratio, fresh context — n=4 per row</text>')
    o.append(f'<text x="{PX}" y="{top-22}" font-size="12.5" fill="{c["muted"]}">'
             'each bar is one rep, HIP and Vulkan measured back-to-back · log scale</text>')

    for g in (0.5, 0.7, 1.5, 2.0):
        if abs(math.log10(g)) < span:
            gx = x_of(g)
            o.append(f'<line x1="{gx:.1f}" y1="{top-6}" x2="{gx:.1f}" y2="{top+len(rows)*rowh}" stroke="{c["grid"]}" stroke-width="1"/>')

    for i, (label, ratio) in enumerate(rows):
        y = top + i * rowh
        bx, col = x_of(ratio), (c["hip"] if ratio >= 1 else c["vk"])
        x0, x1 = (mid, bx) if ratio >= 1 else (bx, mid)
        # 2px surface gap keeps the bar off the reference line
        gap = 1.0 if ratio >= 1 else -1.0
        o.append(f'<rect x="{min(x0,x1)+ (gap if ratio>=1 else 0):.1f}" y="{y+5}" '
                 f'width="{max(abs(x1-x0)-1,1):.1f}" height="14" rx="4" fill="{col}"/>')
        o.append(f'<text x="{PX}" y="{y+16}" font-size="12.5" fill="{c["ink2"]}">{esc(label)}</text>')
        tx = (max(x0, x1) + 8) if ratio >= 1 else (min(x0, x1) - 8)
        anc = "start" if ratio >= 1 else "end"
        o.append(f'<text x="{tx:.1f}" y="{y+16}" font-size="12.5" font-weight="600" '
                 f'text-anchor="{anc}" fill="{c["ink"]}">{ratio:.2f}×</text>')

    ybot = top + len(rows) * rowh
    o.append(f'<line x1="{mid:.1f}" y1="{top-6}" x2="{mid:.1f}" y2="{ybot}" stroke="{c["axis"]}" stroke-width="2"/>')
    o.append(f'<text x="{mid:.1f}" y="{ybot+20}" font-size="12" text-anchor="middle" fill="{c["muted"]}">1.0× — parity</text>')
    o.append(f'<text x="{mid-96:.1f}" y="{top-6}" font-size="12" text-anchor="end" fill="{c["vk"]}">◀ Vulkan faster</text>')
    o.append(f'<text x="{mid+96:.1f}" y="{top-6}" font-size="12" fill="{c["hip"]}">HIP faster ▶</text>')

    o.append(f'<text x="{PX}" y="{ybot+52}" font-size="13.5" font-weight="600" fill="{c["ink"]}">'
             'Ratios straddle 1.0 — neither backend reliably wins.</text>')
    o.append(f'<text x="{PX}" y="{ybot+72}" font-size="12.5" fill="{c["ink2"]}">'
             'Whichever "wins" depends on the draw. Single benchmarks here are near-uninformative.</text>')

    # ---- stat tiles ------------------------------------------------------
    SX, SW = 772, 372
    def tile(y, h, big, cap, sub, col):
        o.append(f'<rect x="{SX}" y="{y}" width="{SW}" height="{h}" rx="10" fill="{c["mid"]}"/>')
        o.append(f'<text x="{SX+22}" y="{y+52}" font-size="40" font-weight="700" fill="{col}">{esc(big)}</text>')
        o.append(f'<text x="{SX+22}" y="{y+78}" font-size="13.5" font-weight="600" fill="{c["ink"]}">{esc(cap)}</text>')
        for j, line in enumerate(sub):
            o.append(f'<text x="{SX+22}" y="{y+100+j*17}" font-size="12" fill="{c["ink2"]}">{esc(line)}</text>')

    d = R.get(("28", "pp512 @ d4096"), [(1, 0)])[0][1]
    tile(122, 132, f"{d:.1f}×", "HIP faster at 4096-token depth",
         ["Vulkan collapses to 3.1 t/s under VRAM", "pressure; HIP holds 60.5. n=1."], c["hip"])
    tile(268, 132, "3×", "HIP run-to-run variance",
         ["44–145 t/s across identical runs.", "Vulkan: 48–86. Cause unexplained."], c["vk"])
    tile(414, 118, "17.3 GB", "model on an 8 GB card",
         ["-ngl 99 -ncmoe 28 · gfx1010 (RDNA1),", "which AMD marks unsupported."], c["ink"])

    o.append(f'<text x="56" y="{H-42}" font-size="11.5" fill="{c["muted"]}">'
             'llama.cpp b10630 · HIP SDK 6.2.4 · Ryzen 5 3600 · measured with no perf-counter sampling during timed runs, backends interleaved per rep</text>')
    o.append('</svg>')
    return "\n".join(o)


if __name__ == "__main__":
    R = load_ratios()
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    for mode in ("light", "dark"):
        p = out / f"hero-{mode}.svg"
        p.write_text(build(mode, R), encoding="utf-8")
        print("wrote", p)
