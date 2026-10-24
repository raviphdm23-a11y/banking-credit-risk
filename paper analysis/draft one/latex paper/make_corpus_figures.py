"""make_corpus_figures.py - regenerate the corpus figures for the IEEE TAI paper.

Single source of truth for the three data-driven corpus figures, so they are
reproducible (the originals were built by an uncommitted scratchpad script).
Every number below traces to a committed record: tab:corpus / tab:riley in
main.tex and the per-dataset SHARP_/AEGIS_RUN_ records. EPV uses the paper's
convention = events / SELECTED columns.

Run from this directory:
    ..\..\..\venv310\Scripts\python.exe make_corpus_figures.py

Emits: corpus_gini.pdf, fig_signal_volume.pdf, fig_riley_headroom.pdf
(fig_fairness_air.pdf and reliability.pdf are unaffected by Polish/mortgage and
are NOT regenerated here.)
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
def _out(name):
    return os.path.join(HERE, name)

# name, N, base_rate, pool, sel, gini, auc, N_req(Riley), verdict ('GO'|'NO-GO')
# fairness_live only affects fig_fairness_air (not built here).
CORPUS = [
    ("SBA",        2102,   0.326, 19, 11, 0.86, 0.93, 338,  "GO"),
    ("HMEQ",       5960,   0.200, 12, 11, 0.81, 0.91, 278,  "GO"),
    ("POLISH",     7027,   0.039, 64, 37, 0.78, 0.89, 5141, "GO"),   # added #13
    ("CREDITRISK", 32581,  0.218, 9,  6,  0.76, 0.88, 263,  "GO"),
    ("GMSC",       149391, 0.067, 9,  8,  0.70, 0.85, 570,  "GO"),
    ("HELOC",      10459,  0.522, 23, 17, 0.59, 0.79, 522,  "GO"),
    ("TAIWAN",     30000,  0.221, 20, 14, 0.54, 0.77, 737,  "GO"),
    ("GERMAN",     1000,   0.300, 17, 5,  0.54, 0.77, 323,  "GO"),
    ("MORTGAGE",   50049,  0.303, 10, 6,  0.46, 0.73, 358,  "GO"),   # added #14
    ("MSME",       1707,   0.060, 87, 15, 0.43, 0.72, 3654, "NO-GO"),
    ("LC",         39717,  0.142, 21, 9,  0.36, 0.68, 1581, "GO"),
    ("LOAN",       9578,   0.160, 13, 7,  0.34, 0.67, 1220, "GO"),
    ("TH02",       1225,   0.264, 14, 6,  0.27, 0.64, 1170, "GO"),
    ("PAK",        50000,  0.261, 39, 6,  0.15, 0.57, 4041, "NO-GO"),
]

GO_C   = "#2b6cb0"   # GO-with-conditions
NOGO_C = "#c0392b"   # NO-GO
plt.rcParams.update({"font.size": 9, "font.family": "serif",
                     "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})

def _color(v):
    return NOGO_C if v == "NO-GO" else GO_C


def fig_corpus_gini():
    rows = sorted(CORPUS, key=lambda r: r[5])  # ascending Gini -> top is highest
    names = [r[0] for r in rows]; ginis = [r[5] for r in rows]
    cols = [_color(r[8]) for r in rows]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    y = range(len(rows))
    ax.barh(list(y), ginis, color=cols, height=0.68)
    for i, g in enumerate(ginis):
        ax.text(g + 0.008, i, f"{g:.2f}", va="center", fontsize=7.5)
    ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=7.8)
    ax.set_xlabel("Selection-stage Gini (out-of-fold)")
    ax.set_xlim(0, 0.95)
    h = [plt.Rectangle((0, 0), 1, 1, color=GO_C),
         plt.Rectangle((0, 0), 1, 1, color=NOGO_C)]
    ax.legend(h, ["GO-with-conditions", "NO-GO"], loc="lower right",
              frameon=False, fontsize=7.5)
    fig.savefig(_out("corpus_gini.pdf")); plt.close(fig)


def fig_signal_volume():
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for name, N, base, pool, sel, gini, auc, nreq, v in CORPUS:
        ax.scatter(N, gini, c=_color(v), s=34, zorder=3,
                   edgecolor="white", linewidth=0.5)
        dx = 1.05
        ha = "left"
        if name in ("GMSC", "PAK", "MORTGAGE", "LC"):
            ha = "right"; dx = 0.95
        ax.annotate(name, (N * dx, gini), fontsize=6.8, va="center", ha=ha)
    ax.set_xscale("log")
    ax.set_xlabel("Sample size $N$ (log scale)")
    ax.set_ylabel("Selection-stage Gini")
    ax.set_ylim(0, 0.95)
    h = [plt.Line2D([], [], marker="o", ls="", color=GO_C, label="GO-with-conditions"),
         plt.Line2D([], [], marker="o", ls="", color=NOGO_C, label="NO-GO")]
    ax.legend(handles=h, loc="upper right", frameon=False, fontsize=7.5)
    fig.savefig(_out("fig_signal_volume.pdf")); plt.close(fig)


def fig_riley_headroom():
    rows = sorted(CORPUS, key=lambda r: r[1] / r[7])  # ascending headroom
    names = [r[0] for r in rows]
    head = [r[1] / r[7] for r in rows]
    cols = [(NOGO_C if hr < 1.0 else GO_C) for hr in head]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    y = range(len(rows))
    ax.barh(list(y), head, color=cols, height=0.68)
    ax.axvline(1.0, ls="--", color="#555", lw=1)
    for i, hr in enumerate(head):
        ax.text(hr * 1.06, i, (f"{hr:.2f}×" if hr < 10 else f"{hr:.0f}×"),
                va="center", fontsize=7)
    ax.set_xscale("log")
    ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=7.8)
    ax.set_xlabel("Headroom = rows available / Riley minimum required (log scale)")
    ax.set_xlim(0.3, 600)
    ax.text(1.02, len(rows) - 0.4, "meets minimum (1×)", fontsize=6.6,
            color="#555", rotation=90, va="top")
    fig.savefig(_out("fig_riley_headroom.pdf")); plt.close(fig)


if __name__ == "__main__":
    fig_corpus_gini()
    fig_signal_volume()
    fig_riley_headroom()
    print("wrote corpus_gini.pdf, fig_signal_volume.pdf, fig_riley_headroom.pdf (14 datasets)")
