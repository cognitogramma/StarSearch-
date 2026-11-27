"""Feasibility run: period posterior + held-out prediction for Gaia DR3 EBs.

For each star in data/stars.csv and each K in (1, 3):
  1. hide the last third of the time span; fit the first two thirds
  2. grid posterior over (f = 1/P, ln s)          -- reference
  3. Metropolis-Hastings over (ln P, ln s)         -- method under test
  4. compare MH and grid mode probabilities
  5. posterior predictive for hidden points; 68%/95% coverage and log
     predictive density, vs a constant-flux (K = 0) baseline

Gaia's catalogue frequency is read only in `report()`, after all fitting.
Outputs: figs/*.png, results.json.     Runtime: a few minutes.
"""
import csv
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import model as M

HERE = Path(__file__).resolve().parent
DATA, FIGS = HERE / "data", HERE / "figs"
KS = (1, 3)
N_CHAINS, N_ITER, BURN = 24, 40000, 10000
N_PRED_DRAWS = 400

C_TRAIN, C_TEST, C_GRID, C_MH, C_GAIA = "#2b6cb0", "#dd6b20", "#1a202c", "#38a169", "#c53030"


def load_star(sid):
    a = np.loadtxt(DATA / f"lc_{sid}.csv", delimiter=",", skiprows=1)
    t, flux, err = a[:, 0], a[:, 1], a[:, 2]
    t_cut = t.min() + 2 / 3 * (t.max() - t.min())
    tr = t < t_cut
    norm = np.median(flux[tr])                      # training data only
    return dict(t=t, y=flux / norm, sig=err / norm, train=tr, test=~tr,
                t_cut=t_cut, norm=norm)


def fit_star(lc, K, seed):
    tr, te = lc["train"], lc["test"]
    t, y, sig = lc["t"][tr], lc["y"][tr], lc["sig"][tr]
    t0 = time.time()
    grid = M.grid_posterior(t, y, sig, K)
    t_grid = time.time() - t0
    t0 = time.time()
    mh = M.run_mh(t, y, sig, K, n_chains=N_CHAINS, n_iter=N_ITER, seed=seed)
    t_mh = time.time() - t0

    post = mh["chain"][BURN:]                                   # (iter, chain, 2)
    f_mh = np.exp(-post[..., 0])
    modes = M.find_modes(grid["freqs"], grid["pf"])
    top = modes[:5]
    mh_mass = M.mode_masses_from_samples(f_mh.ravel(), top)
    # per-chain: which grid mode does each chain spend most of its time in
    chain_mode = []
    for c in range(N_CHAINS):
        m = M.mode_masses_from_samples(f_mh[:, c], top)
        chain_mode.append(int(np.argmax(m)) if m.max() > 0.5 else -1)

    # posterior predictive from MH draws (method) and from grid draws (reference)
    rng = np.random.default_rng(seed + 100)
    flat = post.reshape(-1, 2)
    d = flat[rng.choice(len(flat), N_PRED_DRAWS, replace=False)]
    args = (t, y, sig, lc["t"][te], lc["sig"][te])
    pred_mh = M.predictive(*args, d[:, 0], d[:, 1], K, seed=seed)
    cov_mh = M.coverage_and_lpd(lc["y"][te], pred_mh["mu"], pred_mh["var"], pred_mh["q"])

    idx = rng.choice(grid["mass"].size, N_PRED_DRAWS, p=grid["mass"].ravel())
    fi, si = np.unravel_index(idx, grid["mass"].shape)
    pred_gr = M.predictive(*args, -np.log(grid["freqs"][fi]), grid["lns"][si], K, seed=seed)
    cov_gr = M.coverage_and_lpd(lc["y"][te], pred_gr["mu"], pred_gr["var"], pred_gr["q"])

    return dict(K=K, grid=grid, mh=mh, f_mh=f_mh, lns_mh=post[..., 1], modes=top,
                mh_mass=mh_mass, chain_mode=chain_mode, pred=pred_mh, cov=cov_mh,
                cov_grid=cov_gr, t_grid=t_grid, t_mh=t_mh)


def baseline(lc):
    """Constant flux + jitter (K = 0): what you'd predict knowing nothing about P."""
    tr, te = lc["train"], lc["test"]
    t, y, sig = lc["t"][tr], lc["y"][tr], lc["sig"][tr]
    lns = np.linspace(M.LNS_MIN, M.LNS_MAX, 400)
    lw = M.log_marg_like(t, y, sig, np.ones_like(lns), np.exp(lns), 0) + M.log_prior_lns(lns)
    w = np.exp(lw - lw.max()); w /= w.sum()
    rng = np.random.default_rng(0)
    draws = rng.choice(lns, N_PRED_DRAWS, p=w)
    pred = M.predictive(t, y, sig, lc["t"][te], lc["sig"][te],
                        np.zeros(N_PRED_DRAWS), draws, 0)
    return M.coverage_and_lpd(lc["y"][te], pred["mu"], pred["var"], pred["q"])


# --- plots --------------------------------------------------------------------
def plot_star(sid, lc, fits, gaia_f):
    fig = plt.figure(figsize=(13, 3.1 * (1 + len(fits))), constrained_layout=True)
    gs = fig.add_gridspec(1 + len(fits), 3)
    tr, te = lc["train"], lc["test"]

    ax = fig.add_subplot(gs[0, :])
    ax.errorbar(lc["t"][tr], lc["y"][tr], lc["sig"][tr], fmt="o", ms=4, color=C_TRAIN,
                label=f"fit ({tr.sum()} pts)")
    ax.errorbar(lc["t"][te], lc["y"][te], lc["sig"][te], fmt="s", ms=4, color=C_TEST,
                label=f"held out ({te.sum()} pts)")
    ax.axvline(lc["t_cut"], color="0.5", ls="--", lw=1)
    ax.set(xlabel="BJD − 2455197.5 [d]", ylabel="G flux / median",
           title=f"Gaia DR3 {sid} — G-band light curve")
    ax.legend(loc="lower left", frameon=False)

    for row, fit in enumerate(fits, start=1):
        K, g = fit["K"], fit["grid"]
        P = 1 / g["freqs"]
        # (a) full posterior over log P: grid density vs MH histogram
        ax = fig.add_subplot(gs[row, 0])
        lnP = np.log(P)
        dens = g["pf"] / (np.abs(np.gradient(lnP)))
        ax.plot(P, dens / dens.max(), color=C_GRID, lw=0.8, label="grid")
        bins = np.linspace(M.LNP_MIN, M.LNP_MAX, 600)
        h, e = np.histogram(np.log(1 / fit["f_mh"].ravel()), bins=bins, density=True)
        ax.stairs(h / h.max(), np.exp(e), color=C_MH, alpha=0.8, label="MH")
        ax.set_xscale("log")
        ax.set(xlabel="P [d]", ylabel="posterior (peak = 1)", title=f"K = {K}: P posterior")
        for mult, ls in [(1, "-"), (0.5, ":"), (2, ":")]:
            ax.axvline(mult / gaia_f, color=C_GAIA, ls=ls, lw=1)
        ax.legend(frameon=False, fontsize=8, loc="upper left")

        # (b) mode probabilities, grid vs MH
        ax = fig.add_subplot(gs[row, 1])
        x = np.arange(len(fit["modes"]))
        ax.bar(x - 0.2, [m["mass"] for m in fit["modes"]], 0.4, color=C_GRID, label="grid")
        ax.bar(x + 0.2, fit["mh_mass"], 0.4, color=C_MH, label="MH")
        ax.set_xticks(x, [f"{m['P_peak']:.4g} d" for m in fit["modes"]], fontsize=8)
        ax.set(ylabel="probability", ylim=(0, 1), title=f"K = {K}: top modes (red = Gaia P)")
        for i, m in enumerate(fit["modes"]):
            if abs(m["P_peak"] * gaia_f - 1) < 0.01:
                ax.get_xticklabels()[i].set_color(C_GAIA)
        ax.legend(frameon=False, fontsize=8)

        # (c) predictive band vs hidden data, folded on the top-mode period
        ax = fig.add_subplot(gs[row, 2])
        Pbest = fit["modes"][0]["P_peak"]
        ph_tr = (lc["t"][tr] / Pbest) % 1
        ph_te = (lc["t"][te] / Pbest) % 1
        q = fit["pred"]["q"]
        o = np.argsort(ph_te)
        ax.plot(ph_tr, lc["y"][tr], "o", ms=3, color=C_TRAIN, alpha=0.5, label="fit data")
        ax.vlines(ph_te[o], q[0][o], q[4][o], color=C_TEST, alpha=0.25, lw=5, label="95% band")
        ax.vlines(ph_te[o], q[1][o], q[3][o], color=C_TEST, alpha=0.55, lw=5, label="68% band")
        inn = fit["cov"]["in95"]
        ax.plot(ph_te[inn], lc["y"][te][inn], "s", ms=4, color="k", label="hidden, in 95%")
        ax.plot(ph_te[~inn], lc["y"][te][~inn], "x", ms=6, color=C_GAIA, label="hidden, outside")
        ax.set(xlabel=f"phase at P = {Pbest:.5g} d", ylabel="G flux / median",
               title=f"K = {K}: 68% {fit['cov']['cov68']:.0%}, 95% {fit['cov']['cov95']:.0%}")
        ax.legend(frameon=False, fontsize=7, loc="lower left")
    fig.savefig(FIGS / f"star_{sid}.png", dpi=130)
    plt.close(fig)


def plot_summary(results):
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6), constrained_layout=True)
    labels = [str(r["source_id"])[-6:] for r in results]
    x = np.arange(len(results))
    for j, (key, lvl) in enumerate([("cov68", 0.68), ("cov95", 0.95)]):
        for i, (K, c) in enumerate([(0, "0.6"), (1, C_TRAIN), (3, C_TEST)]):
            vals = [r["baseline"][key] if K == 0 else r[f"K{K}"]["holdout"][key] for r in results]
            ax[j].bar(x + (i - 1) * 0.27, vals, 0.27, color=c,
                      label="constant (K=0)" if K == 0 else f"K = {K}")
        ax[j].axhline(lvl, color="k", ls="--", lw=1)
        ax[j].set_xticks(x, labels)
        ax[j].set(ylim=(0, 1.05), ylabel="fraction of hidden points inside",
                  title=f"{int(lvl * 100)}% band coverage (dashed = nominal)", xlabel="source_id (last 6 digits)")
    ax[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.savefig(FIGS / "coverage_summary.png", dpi=130)
    plt.close(fig)


# --- report -------------------------------------------------------------------
def report(sid, lc, fits, base):
    gaia = {int(r["source_id"]): r for r in csv.DictReader(open(DATA / "stars.csv"))}[sid]
    gaia_f = float(gaia["gaia_frequency"])
    out = dict(source_id=sid, n_train=int(lc["train"].sum()), n_test=int(lc["test"].sum()),
               train_span_d=float(np.ptp(lc["t"][lc["train"]])),
               gaia_period_d=1 / gaia_f, gaia_model_type=gaia["model_type"],
               baseline={k: base[k] for k in ("cov68", "cov95", "lpd_per_point")})
    print(f"\n=== {sid}  (n_fit={out['n_train']}, n_hidden={out['n_test']}, "
          f"Gaia P = {1 / gaia_f:.5f} d, {gaia['model_type']})")
    print(f"  baseline K=0: 68% {base['cov68']:.0%}  95% {base['cov95']:.0%}  "
          f"lpd/pt {base['lpd_per_point']:+.2f}")
    for fit in fits:
        modes = []
        for m, mh in zip(fit["modes"], fit["mh_mass"]):
            ratio = m["P_peak"] * gaia_f
            modes.append(dict(P_d=m["P_peak"], prob_grid=m["mass"], prob_mh=float(mh),
                              P_over_gaiaP=ratio))
        pg = np.array([m["prob_grid"] for m in modes]); pm = np.array([m["prob_mh"] for m in modes])
        tv = 0.5 * (np.abs(pg - pm).sum() + abs((1 - pg.sum()) - (1 - pm.sum())))
        r = dict(modes=modes, mh_vs_grid_tv_top5=float(tv),
                 mh_acceptance=float(fit["mh"]["acc_total"]),
                 mh_acceptance_by_move=dict(zip(
                     [f"rw_{s:g}" for s in M.RW_SCALES_LNP] + ["jump_ln2"],
                     map(float, fit["mh"]["acc_by_move"]))),
                 chains_in_top_mode=int(sum(c == 0 for c in fit["chain_mode"])),
                 chains_unsettled=int(sum(c == -1 for c in fit["chain_mode"])),
                 s_median=float(np.exp(np.median(fit["lns_mh"]))),
                 holdout={k: fit["cov"][k] for k in ("cov68", "cov95", "lpd_per_point")},
                 holdout_grid_draws={k: fit["cov_grid"][k] for k in ("cov68", "cov95", "lpd_per_point")},
                 runtime_s=dict(grid=fit["t_grid"], mh=fit["t_mh"]))
        out[f"K{fit['K']}"] = r
        print(f"  K={fit['K']}: acc {r['mh_acceptance']:.0%}, chains in top mode "
              f"{r['chains_in_top_mode']}/{N_CHAINS}, TV(MH,grid) {tv:.3f}, s~{r['s_median']:.3g}")
        for m in modes:
            print(f"     P = {m['P_d']:9.5f} d   grid {m['prob_grid']:.3f}   MH {m['prob_mh']:.3f}"
                  f"   P/P_gaia = {m['P_over_gaiaP']:.4f}")
        h = r["holdout"]
        print(f"     hidden: 68% {h['cov68']:.0%}  95% {h['cov95']:.0%}  lpd/pt {h['lpd_per_point']:+.2f}"
              f"   (grid draws: {r['holdout_grid_draws']['cov68']:.0%} / "
              f"{r['holdout_grid_draws']['cov95']:.0%})")
    plot_star(sid, lc, fits, gaia_f)
    return out


def main():
    FIGS.mkdir(exist_ok=True)
    sids = [int(r["source_id"]) for r in csv.DictReader(open(DATA / "stars.csv"))]
    results = []
    for i, sid in enumerate(sids):
        lc = load_star(sid)
        fits = [fit_star(lc, K, seed=10 * i + K) for K in KS]   # no Gaia info used here
        results.append(report(sid, lc, fits, baseline(lc)))
    plot_summary(results)
    with open(HERE / "results.json", "w") as fh:
        json.dump(results, fh, indent=1)


if __name__ == "__main__":
    main()
