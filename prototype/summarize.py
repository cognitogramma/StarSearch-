"""Aggregate results.json from run.py into summary tables and figures.

Prints the numbers quoted in README.md and writes figs/summary_*.png.
"""
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"
C = {"const": "0.6", "old": "#2b6cb0", "new": "#dd6b20", "old_grid": "#2b6cb0", "new_grid": "#dd6b20"}
LABEL = {"const": "constant\n(K=0)", "old": "old, MH", "new": "new, MH",
         "old_grid": "old, grid", "new_grid": "new, grid"}
PRED = ("const", "old", "old_grid", "new", "new_grid")
ALIASES = ["gaia_P", "P/2", "2P", "2P/3", "3P/2", "other"]


def period_fit(r, which):
    return r["fits"]["old"] if which == "old" else r["fits"][f"new_K{r['best_K']}"]


def main():
    res = json.load(open(HERE / "results.json"))
    sets = {"all": res, "sample40": [r for r in res if r["set"] == "sample40"]}
    out = {}
    for set_name, rs in sets.items():
        if not rs:
            continue
        n_te = np.array([r["n_test"] for r in rs])
        s = dict(n_stars=len(rs), n_hidden_points=int(n_te.sum()))
        for m in PRED:
            c68 = np.array([r["holdout"][m]["cov68"] for r in rs])
            c95 = np.array([r["holdout"][m]["cov95"] for r in rs])
            lpd = np.array([r["holdout"][m]["lpd_per_point"] for r in rs])
            lpd0 = np.array([r["holdout"]["const"]["lpd_per_point"] for r in rs])
            calibrated = (np.abs(c68 - 0.68) <= 0.10) & (np.abs(c95 - 0.95) <= 0.10)
            s[m] = dict(pooled_cov68=float((c68 * n_te).sum() / n_te.sum()),
                        pooled_cov95=float((c95 * n_te).sum() / n_te.sum()),
                        median_cov68=float(np.median(c68)), median_cov95=float(np.median(c95)),
                        frac_stars_calibrated_10pt=float(calibrated.mean()),
                        frac_stars_cov95_below_85=float((c95 < 0.85).mean()),
                        median_lpd=float(np.median(lpd)),
                        frac_beats_const=float((lpd > lpd0).mean()) if m != "const" else None,
                        median_dlpd_vs_const=float(np.median(lpd - lpd0)) if m != "const" else None)
        for m in ("old", "new"):
            fits = [period_fit(r, m) for r in rs]
            cats = Counter(f["top_alias"] for f in fits)
            confident = [f for f in fits if f["top_prob"] > 0.9]
            s[m]["top_mode_alias_counts"] = {a: cats.get(a, 0) for a in ALIASES}
            s[m]["n_confident_top_mode"] = len(confident)
            s[m]["n_confident_and_gaia_P"] = sum(f["top_alias"] == "gaia_P" for f in confident)
            s[m]["n_confident_and_other"] = sum(f["top_alias"] == "other" for f in confident)
            s[m]["mean_prob_on_gaia_P"] = float(np.mean([f["prob_on_gaia_P_top5"] for f in fits]))
        # does agreeing with Gaia's period go with better held-out prediction?
        for grp in ("gaia_P", "P/2", "other"):
            g_rs = [r for r in rs if period_fit(r, "new")["top_alias"] == grp]
            if g_rs:
                d = [r["holdout"]["new_grid"]["lpd_per_point"] - r["holdout"]["const"]["lpd_per_point"]
                     for r in g_rs]
                s.setdefault("new_grid_by_top_alias", {})[grp] = dict(
                    n=len(g_rs), frac_beats_const=float(np.mean(np.array(d) > 0)),
                    median_dlpd_vs_const=float(np.median(d)),
                    median_cov95=float(np.median([r["holdout"]["new_grid"]["cov95"] for r in g_rs])))
        # what fraction of stars would pass the +/-10-point test if perfectly calibrated?
        sim = np.random.default_rng(0)
        k68 = sim.binomial(n_te[None, :], 0.68, size=(4000, n_te.size)) / n_te
        k95 = sim.binomial(n_te[None, :], 0.95, size=(4000, n_te.size)) / n_te
        s["chance_frac_calibrated_10pt_if_perfect"] = float(
            ((np.abs(k68 - 0.68) <= 0.1) & (np.abs(k95 - 0.95) <= 0.1)).mean())
        s["best_K_counts"] = dict(Counter(str(r["best_K"]) for r in rs))
        tvs = np.array([f["mh_vs_grid_tv_top5"] for r in rs for f in r["fits"].values()])
        s["mh_vs_grid"] = dict(n_fits=int(tvs.size), median_tv=float(np.median(tvs)),
                               frac_tv_below_0_05=float((tvs < 0.05).mean()),
                               frac_tv_below_0_1=float((tvs < 0.1).mean()),
                               max_tv=float(tvs.max()))
        out[set_name] = s
    json.dump(out, open(HERE / "summary.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
    plots(res)


def plots(res):
    rs = res
    n = len(rs)
    # coverage per star
    fig, ax = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    rng = np.random.default_rng(0)
    for j, (key, lvl) in enumerate([("cov68", 0.68), ("cov95", 0.95)]):
        for i, m in enumerate(PRED):
            v = np.array([r["holdout"][m][key] for r in rs])
            ax[j].scatter(i + rng.uniform(-0.18, 0.18, n), v, s=14, color=C[m],
                          alpha=0.35 if m in ("old", "new") else 0.75)
            ax[j].plot([i - 0.3, i + 0.3], [np.median(v)] * 2, color="k", lw=2)
        ax[j].axhspan(lvl - 0.1, lvl + 0.1, color="#38a169", alpha=0.12, lw=0)
        ax[j].axhline(lvl, color="#38a169", ls="--", lw=1)
        ax[j].set_xticks(range(len(PRED)), [LABEL[m] for m in PRED], fontsize=8)
        ax[j].set(ylim=(-0.03, 1.03), ylabel="fraction of hidden points inside",
                  title=f"{int(lvl * 100)}% band coverage per star (green = nominal ± 10 pts, bar = median)")
        ax[j].title.set_fontsize(9)
    fig.savefig(FIGS / "summary_coverage.png", dpi=130)
    plt.close(fig)

    # lpd vs constant baseline
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    d_old = np.array([r["holdout"]["old_grid"]["lpd_per_point"] - r["holdout"]["const"]["lpd_per_point"] for r in rs])
    d_new = np.array([r["holdout"]["new_grid"]["lpd_per_point"] - r["holdout"]["const"]["lpd_per_point"] for r in rs])
    lim = np.percentile(np.abs(np.r_[d_old, d_new]), 97) * 1.1
    ax.scatter(np.clip(d_old, -lim, lim), np.clip(d_new, -lim, lim), s=18, color=C["new"])
    ax.axhline(0, color="0.5", lw=1); ax.axvline(0, color="0.5", lw=1)
    ax.plot([-lim, lim], [-lim, lim], color="0.7", ls=":", lw=1)
    ax.set(xlim=(-lim, lim), ylim=(-lim, lim),
           xlabel="old − constant: held-out lpd per point", ylabel="new − constant: held-out lpd per point",
           title="Held-out log predictive density relative to a constant model\n"
                 "(grid draws; right / up = beats constant; above diagonal = new beats old; clipped)")
    ax.title.set_fontsize(9)
    fig.savefig(FIGS / "summary_lpd.png", dpi=130)
    plt.close(fig)

    # period recovery
    fig, ax = plt.subplots(figsize=(7, 3.6), constrained_layout=True)
    for i, m in enumerate(("old", "new")):
        left = 0
        for a, col in zip(ALIASES, ["#38a169", "#90cdf4", "#4299e1", "#b794f4", "#805ad5", "#c53030"]):
            fits = [period_fit(r, m) for r in rs]
            k_conf = sum(f["top_alias"] == a and f["top_prob"] > 0.9 for f in fits)
            k_unc = sum(f["top_alias"] == a and f["top_prob"] <= 0.9 for f in fits)
            ax.barh(i, k_conf, left=left, color=col, label=a if i == 0 else None)
            ax.barh(i, k_unc, left=left + k_conf, color=col, alpha=0.4, hatch="//")
            left += k_conf + k_unc
    ax.set_yticks([0, 1], ["old: flat K=3", "new: shrinkage, best K"])
    ax.set(xlabel="number of stars",
           title="Top posterior mode vs Gaia's period (solid: top-mode prob > 0.9; hatched: less)")
    ax.title.set_fontsize(9)
    ax.legend(ncol=6, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    fig.savefig(FIGS / "summary_periods.png", dpi=130)
    plt.close(fig)

    # MH vs grid
    fig, ax = plt.subplots(figsize=(6, 3.4), constrained_layout=True)
    tvs = np.array([f["mh_vs_grid_tv_top5"] for r in rs for f in r["fits"].values()])
    ax.hist(tvs, bins=np.linspace(0, max(0.5, tvs.max()), 41), color="#38a169")
    ax.set(xlabel="total-variation distance between MH and grid mode probabilities",
           ylabel="fits", title=f"MH vs grid, all {tvs.size} fits (4 models × {n} stars)")
    ax.title.set_fontsize(9)
    fig.savefig(FIGS / "summary_mh_vs_grid.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
