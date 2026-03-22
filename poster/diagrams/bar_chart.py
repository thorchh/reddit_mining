"""Generate mean sycophancy score bar chart for CliniSyc poster."""

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from pathlib import Path

# ── Data: mean sycophancy score (0–10) from evaluation output ──
models = ["Qwen3\n30B-A3B", "Qwen2.5\n14B", "Mistral\nSmall 24B", "Phi-4", "Qwen2.5\n7B"]
baseline =      [2.6, 3.4, 3.2, 3.4, 4.0]
empathy_first = [3.2, 4.2, 4.2, 4.2, 4.3]
n_per_cell = 10

# ── Style ──────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 13,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
})

fig, ax = plt.subplots(figsize=(7, 4.5))

x = np.arange(len(models))
width = 0.33

bars1 = ax.bar(x - width / 2, baseline, width,
               label="Baseline", color="#90CAF9", edgecolor="#1565C0", linewidth=1.2)
bars2 = ax.bar(x + width / 2, empathy_first, width,
               label="Empathy-first", color="#EF9A9A", edgecolor="#C62828", linewidth=1.2)

# ── Labels on bars ─────────────────────────────────────────────
for bar in bars1:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.12, f"{h:.1f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#1565C0")

for bar in bars2:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.12, f"{h:.1f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#C62828")

# ── Axes ───────────────────────────────────────────────────────
ax.set_ylabel("Mean Sycophancy Score", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(models, fontsize=11)
ax.set_ylim(0, 6)
ax.set_yticks([0, 1, 2, 3, 4, 5, 6])

ax.legend(fontsize=12, loc="upper left", frameon=False)

ax.text(0.98, 0.02, f"n = {n_per_cell} per cell  |  scale: 0 (none) – 10 (extreme)",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=9, color="#666", style="italic")

plt.tight_layout()

# ── Save ───────────────────────────────────────────────────────
out_dir = Path(__file__).parent
fig.savefig(out_dir / "bar_chart.pdf", bbox_inches="tight")
fig.savefig(out_dir / "bar_chart.png", bbox_inches="tight", dpi=300)
print(f"Saved to {out_dir / 'bar_chart.pdf'} and {out_dir / 'bar_chart.png'}")
plt.close()
