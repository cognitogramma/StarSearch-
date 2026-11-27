"""Summarise the 100k-star survey: recovery rates, failure modes, and whether the
posterior probabilities are calibrated. Writes results/survey_summary.json and
figs/survey_*.png."""
import json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, AQUA, YELLOW, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#1b1b1b", "#5c5b57", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
                     "savefig.dpi": 200, "savefig.bbox": "tight", "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED})

d = pd.read_csv("results/survey_dr2.csv")
d = d[d.status == "ok"].copy()
d["right"] = d.rel.isin(["match", "half", "double"])     # right period up to the usual factor 2
d["exact"] = d.rel == "match"
S = {"n_stars": int(len(d))}

# --- 1. recovery by type --------------------------------------------------
order = ["RR", "RRc", "CEP", "CEPII", "EW", "EA", "RSCVN", "BYDra"]
tab = (d.groupby("Type").rel.value_counts(normalize=True).unstack().fillna(0)
       .reindex(order).reindex(columns=["match", "half", "double", "alias", "alias2x", "other"], fill_value=0))
S["by_type"] = {t: {k: round(float(v), 4) for k, v in row.items()} for t, row in tab.iterrows()}
S["by_type_n"] = d.Type.value_counts().to_dict()

fig, ax = plt.subplots(figsize=(10, 4.8))
cols = {"match": INK, "half": BLUE, "double": "#6da7ec", "alias": ORANGE, "alias2x": YELLOW, "other": "#c3c2b7"}
left = np.zeros(len(tab))
for k in tab.columns:
    ax.barh(tab.index, tab[k], left=left, color=cols[k], label=k, edgecolor="white", linewidth=1)
    left += tab[k].values
ax.invert_yaxis(); ax.set_xlim(0, 1); ax.set_xlabel("fraction of stars")
ax.set_title("What the sampler's top period is, relative to the catalogue")
ax.legend(ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.32), fontsize=11)
fig.savefig("figs/survey_by_type.png"); plt.close(fig)

# --- 2. calibration: when the posterior says p, is it right p of the time? --
pul = d[d.Type.isin(["RR", "RRc", "CEP", "CEPII"])]     # pulsators: catalogue period is the "truth"
bins = np.array([0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001])
pul = pul.assign(b=pd.cut(pul.p1, bins, right=False))
cal = pul.groupby("b", observed=True).agg(n=("exact", "size"), stated=("p1", "mean"), actual=("exact", "mean"))
S["calibration_pulsators"] = [{"stated": round(r.stated, 4), "actual": round(r.actual, 4), "n": int(r.n)}
                              for r in cal.itertuples()]
fig, ax = plt.subplots(figsize=(6, 5.4))
ax.plot([0, 1], [0, 1], color=MUTED, ls="--", lw=1)
ax.scatter(cal.stated, cal.actual, s=np.clip(cal.n / cal.n.max() * 400, 20, 400), color=BLUE, zorder=3)
for r in cal.itertuples():
    ax.annotate(f"n={r.n:,}", (r.stated, r.actual), xytext=(6, -14), textcoords="offset points", fontsize=10, color=MUTED)
ax.set_xlim(0.3, 1.02); ax.set_ylim(0.3, 1.02)
ax.set_xlabel("posterior probability of the top period"); ax.set_ylabel("fraction that match the catalogue")
ax.set_title("Is the posterior honest? (RR Lyrae + Cepheids)")
fig.savefig("figs/survey_calibration.png"); plt.close(fig)

# --- 3. recovery vs number of observations (the "boundary") ---------------
nb = [20, 30, 40, 60, 80, 120, 200, 400, 5000]
pul = pul.assign(nbin=pd.cut(pul.N, nb, right=False))
bn = pul.groupby("nbin", observed=True).agg(n=("exact", "size"), rate=("exact", "mean"), conf=("p1", "mean"))
S["recovery_vs_N_pulsators"] = [{"N_bin": str(i), "n": int(r.n), "match_rate": round(r.rate, 4),
                                 "mean_p1": round(r.conf, 4)} for i, r in zip(bn.index, bn.itertuples())]
fig, ax = plt.subplots(figsize=(8, 4.6))
mid = [f"{a}-{b}" for a, b in zip(nb[:-1], nb[1:])][:len(bn)]
ax.plot(mid, bn.rate, "o-", color=INK, lw=2, label="matches catalogue")
ax.plot(mid, bn.conf, "s--", color=ORANGE, lw=2, label="mean posterior probability")
ax.set_ylim(0, 1.02); ax.set_xlabel("number of ZTF DR2 observations"); ax.set_ylabel("fraction")
ax.set_title("More data, more recoveries: RR Lyrae and Cepheids"); ax.legend(loc="lower right")
plt.setp(ax.get_xticklabels(), rotation=30)
fig.savefig("figs/survey_vs_N.png"); plt.close(fig)

# --- 4. sampler health ----------------------------------------------------
S["sampler"] = {
    "rhat_median": float(d.rhat.median()), "rhat_frac_gt_1.1": float((d.rhat > 1.1).mean()),
    "acc_rw_median": float(d.acc_rw.median()), "acc_ind_median": float(d.acc_ind.median()),
    "mh_vs_quadrature_same_top": float((np.abs(d.f1 - d.f_quad) < 1.5 / d["T"]).mean()),
    "seconds_per_star_median": float(d.seconds.median()),
}
S["overall"] = {"exact_match": float(d.exact.mean()), "right_up_to_factor2": float(d.right.mean()),
                "alias": float(d.rel.isin(["alias", "alias2x"]).mean())}
S["pulsators"] = {"n": int(len(pul)), "exact_match": float(pul.exact.mean()),
                  "alias": float(pul.rel.isin(["alias", "alias2x"]).mean())}
json.dump(S, open("results/survey_summary.json", "w"), indent=2)
print(json.dumps(S, indent=2))
