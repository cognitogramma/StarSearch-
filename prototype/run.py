"""Run 2: period posterior + held-out prediction, old vs improved model, 44 stars.

Models, all fitted to the first two thirds of each light curve:
  old      flat prior, K = 3                       (run 1's best model)
  new      shrinkage prior a_k, b_k ~ N(0, (sigma_h/k)^2), sigma_h marginalized,
           K in {1, 3, 6} averaged by Bayesian evidence (BMA)
  const    constant flux + jitter (K = 0)          baseline
All MH runs use the improved sampler (+/- ln 2 and +/- ln 3/2 jumps).

For every model: grid posterior (reference), MH, MH-vs-grid mode check,
posterior predictive for the hidden last third: 68/95% coverage and log
predictive density.  Gaia's catalogue frequency is read only after all fitting
for a star is done (in `report`).

Outputs: figs/stars/<id>.png, figs/summary_*.png, results.json.
Runtime: ~20-30 min on 4 cores.
"""
import csv
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import logsumexp

import model as M

HERE = Path(__file__).resolve().parent
DATA, FIGS = HERE / "data", HERE / "figs"
N_CHAINS, N_ITER, BURN = 16, 25000, 5000
N_PRED_DRAWS = 400
NEW_KS = (1, 3, 6)
MODELS = {"old": M.Prior.flat(3), **{f"new_K{K}": M.Prior.shrink(K) for K in NEW_KS}}

C_TRAIN, C_TEST, C_GRID, C_MH, C_GAIA = "#2b6cb0", "#dd6b20", "#1a202c", "#38a169", "#c53030"


def load_star(sid):
    a = np.loadtxt(DATA / f"lc_{sid}.csv", delimiter=",", skiprows=1)
    t, flux, err = a[:, 0], a[:, 1], a[:, 2]
    t_cut = t.min() + 2 / 3 * (t.max() - t.min())
    tr = t < t_cut
    norm = np.median(flux[tr])                      # training data only
    return dict(t=t, y=flux / norm, sig=err / norm, train=tr, test=~tr, t_cut=t_cut)


def split(lc):
    tr, te = lc["train"], lc["test"]
    return (lc["t"][tr], lc["y"][tr], lc["sig"][tr]), (lc["t"][te], lc["y"][te], lc["sig"][te])


def fit_model(lc, prior, seed):
    (t, y, sig), _ = split(lc)
    t0 = time.time()
    grid = M.grid_posterior(t, y, sig, prior)
    t_grid = time.time() - t0
    t0 = time.time()
    mh = M.run_mh(t, y, sig, prior, n_chains=N_CHAINS, n_iter=N_ITER, seed=seed)
    t_mh = time.time() - t0
    post = mh["chain"][BURN:]
    f_mh = np.exp(-post[..., 0])
    modes = M.find_modes(grid["freqs"], grid["pf"])[:5]
    mh_mass = M.mode_masses_from_samples(f_mh.ravel(), modes)
    pg = np.array([m["mass"] for m in modes])
    tv = 0.5 * (np.abs(pg - mh_mass).sum() + abs(mh_mass.sum() - pg.sum()))
    chain_mode = []
    for c in range(N_CHAINS):
        m = M.mode_masses_from_samples(f_mh[:, c], modes)
        chain_mode.append(int(np.argmax(m)) if m.max() > 0.5 else -1)
    return dict(prior=prior, grid=grid, draws=post.reshape(-1, 2), f_mh=f_mh, modes=modes,
                mh_mass=mh_mass, tv=float(tv), chain_mode=chain_mode, mh=mh,
                t_grid=t_grid, t_mh=t_mh)


def predict(lc, fit, n, rng):
    (t, y, sig), (tt, yt, st) = split(lc)
    d = fit["draws"][rng.choice(len(fit["draws"]), n, replace=False)]
    return M.predictive_components(t, y, sig, tt, st, d[:, 0], d[:, 1], fit["prior"], rng)


def baseline(lc, rng):
    (t, y, sig), (tt, yt, st) = split(lc)
    prior = M.Prior.flat(0)
    lns = np.linspace(M.LNS_MIN, M.LNS_MAX, 400)
    lw = M.log_marg_like(t, y, sig, np.ones_like(lns), np.exp(lns), prior) + M.log_prior_lns(lns)
    w = np.exp(lw - lw.max())
    d = rng.choice(lns, N_PRED_DRAWS, p=w / w.sum())
    mu, var = M.predictive_components(t, y, sig, tt, st, np.zeros(N_PRED_DRAWS), d, prior, rng)
    return M.score(yt, mu, var, rng)


def fit_star(sid, seed):
    lc = load_star(sid)
    rng = np.random.default_rng(seed)
    fits = {name: fit_model(lc, pr, seed + i) for i, (name, pr) in enumerate(MODELS.items())}
    yt = lc["y"][lc["test"]]
    preds = {"old": M.score(yt, *predict(lc, fits["old"], N_PRED_DRAWS, rng), rng)}
    # Bayesian model average over K: evidence weights, equal prior over K
    logZ = np.array([fits[f"new_K{K}"]["grid"]["log_evidence"] for K in NEW_KS])
    wK = np.exp(logZ - logsumexp(logZ))
    counts = rng.multinomial(N_PRED_DRAWS, wK)
    mus, vars_ = [], []
    for K, c in zip(NEW_KS, counts):
        if c:
            mu, var = predict(lc, fits[f"new_K{K}"], c, rng)
            mus.append(mu); vars_.append(var)
    preds["new"] = M.score(yt, np.vstack(mus), np.vstack(vars_), rng)
    preds["const"] = baseline(lc, rng)
    return lc, fits, preds, dict(zip(NEW_KS, wK.tolist()))


# --- after fitting: compare with Gaia -------------------------------------------
def classify(P, gaia_P):
    r = P / gaia_P
    for name, target in [("gaia_P", 1.0), ("P/2", 0.5), ("2P", 2.0), ("2P/3", 2 / 3), ("3P/2", 1.5)]:
        if abs(r / target - 1) < 0.01:
            return name
    return "other"


def summarize_fit(fit, gaia_P):
    modes = [dict(P_d=float(m["P_peak"]), prob_grid=float(m["mass"]), prob_mh=float(mh),
                  P_over_gaiaP=float(m["P_peak"] / gaia_P), alias=classify(m["P_peak"], gaia_P))
             for m, mh in zip(fit["modes"], fit["mh_mass"])]
    gaia_mass = float(sum(m["prob_grid"] for m in modes if m["alias"] == "gaia_P"))
    return dict(modes=modes, top_alias=modes[0]["alias"], top_prob=modes[0]["prob_grid"],
                prob_on_gaia_P_top5=gaia_mass, log_evidence=fit["grid"]["log_evidence"],
                mh_vs_grid_tv_top5=fit["tv"], mh_acceptance=fit["mh"]["acc_total"],
                mh_acceptance_by_move={k: float(v) for k, v in fit["mh"]["acc_by_move"].items()},
                chains_in_top_mode=int(sum(c == 0 for c in fit["chain_mode"])),
                grid_freqs_refined=fit["grid"]["n_refined"],
                runtime_s=dict(grid=round(fit["t_grid"], 1), mh=round(fit["t_mh"], 1)))


def report(sid, set_name, lc, fits, preds, wK):
    gaia = {int(r["source_id"]): r for r in csv.DictReader(open(DATA / "stars.csv"))}[sid]
    gaia_P = 1 / float(gaia["gaia_frequency"])
    best_K = max(wK, key=wK.get)
    out = dict(source_id=sid, set=set_name, n_train=int(lc["train"].sum()),
               n_test=int(lc["test"].sum()), gaia_period_d=gaia_P,
               gaia_model_type=gaia["model_type"], gmag=float(gaia["gmag"]),
               evidence_weights_K=wK, best_K=best_K,
               fits={name: summarize_fit(f, gaia_P) for name, f in fits.items()},
               holdout={k: {kk: p[kk] for kk in ("cov68", "cov95", "lpd_per_point")}
                        for k, p in preds.items()})
    plot_star(sid, lc, fits, preds, gaia_P, best_K, wK)
    return out


def plot_star(sid, lc, fits, preds, gaia_P, best_K, wK):
    rows = [("old", "old: flat prior, K = 3", "old"),
            (f"new_K{best_K}", f"new: shrinkage, K = {best_K} (evidence weight {wK[best_K]:.2f})", "new")]
    fig = plt.figure(figsize=(13, 9.3), constrained_layout=True)
    gs = fig.add_gridspec(3, 3)
    tr, te = lc["train"], lc["test"]
    ax = fig.add_subplot(gs[0, :])
    ax.errorbar(lc["t"][tr], lc["y"][tr], lc["sig"][tr], fmt="o", ms=4, color=C_TRAIN,
                label=f"fit ({tr.sum()} pts)")
    ax.errorbar(lc["t"][te], lc["y"][te], lc["sig"][te], fmt="s", ms=4, color=C_TEST,
                label=f"held out ({te.sum()} pts)")
    ax.axvline(lc["t_cut"], color="0.5", ls="--", lw=1)
    ax.set(xlabel="BJD − 2455197.5 [d]", ylabel="G flux / median",
           title=f"Gaia DR3 {sid} — G band (Gaia P = {gaia_P:.5g} d)")
    ax.legend(loc="lower left", frameon=False)
    for row, (key, label, pkey) in enumerate(rows, start=1):
        fit, g = fits[key], fits[key]["grid"]
        P = 1 / g["freqs"]
        ax = fig.add_subplot(gs[row, 0])
        dens = g["pf"] / np.abs(np.gradient(np.log(P)))
        ax.plot(P, dens / dens.max(), color=C_GRID, lw=0.8, label="grid")
        h, e = np.histogram(np.log(1 / fit["f_mh"].ravel()),
                            bins=np.linspace(M.LNP_MIN, M.LNP_MAX, 600), density=True)
        ax.stairs(h / h.max(), np.exp(e), color=C_MH, alpha=0.8, label="MH")
        ax.set_xscale("log")
        for mult, ls in [(1, "-"), (0.5, ":"), (2, ":")]:
            ax.axvline(mult * gaia_P, color=C_GAIA, ls=ls, lw=1)
        ax.set(xlabel="P [d]", ylabel="posterior (peak = 1)", title=label)
        ax.title.set_fontsize(9)
        ax.legend(frameon=False, fontsize=8, loc="upper left")

        ax = fig.add_subplot(gs[row, 1])
        x = np.arange(len(fit["modes"]))
        ax.bar(x - 0.2, [m["mass"] for m in fit["modes"]], 0.4, color=C_GRID, label="grid")
        ax.bar(x + 0.2, fit["mh_mass"], 0.4, color=C_MH, label="MH")
        ax.set_xticks(x, [f"{m['P_peak']:.4g} d" for m in fit["modes"]], fontsize=8)
        for i, m in enumerate(fit["modes"]):
            if classify(m["P_peak"], gaia_P) == "gaia_P":
                ax.get_xticklabels()[i].set_color(C_GAIA)
        ax.set(ylabel="probability", ylim=(0, 1.05),
               title=f"top modes, TV(MH, grid) = {fit['tv']:.3f}  (red = Gaia P)")
        ax.title.set_fontsize(9)
        ax.legend(frameon=False, fontsize=8, loc="upper right")

        ax = fig.add_subplot(gs[row, 2])
        p = preds[pkey]
        Pbest = fit["modes"][0]["P_peak"]
        ph_tr, ph_te = (lc["t"][tr] / Pbest) % 1, (lc["t"][te] / Pbest) % 1
        q = p["q"]
        ax.plot(ph_tr, lc["y"][tr], "o", ms=3, color=C_TRAIN, alpha=0.5, label="fit data")
        ax.vlines(ph_te, q[0], q[4], color=C_TEST, alpha=0.25, lw=5, label="95% band")
        ax.vlines(ph_te, q[1], q[3], color=C_TEST, alpha=0.55, lw=5, label="68% band")
        inn = p["in95"]
        ax.plot(ph_te[inn], lc["y"][te][inn], "s", ms=4, color="k", label="hidden, in 95%")
        ax.plot(ph_te[~inn], lc["y"][te][~inn], "x", ms=6, color=C_GAIA, label="hidden, outside")
        c = preds["const"]
        ax.set(xlabel=f"phase at P = {Pbest:.5g} d", ylabel="G flux / median",
               title=f"{pkey}: cover {p['cov68']:.0%}/{p['cov95']:.0%}, lpd {p['lpd_per_point']:+.2f} "
                     f"(const {c['lpd_per_point']:+.2f})")
        ax.title.set_fontsize(9)
        ax.legend(frameon=False, fontsize=7, loc="lower left")
    fig.savefig(FIGS / "stars" / f"{sid}.png", dpi=110)
    plt.close(fig)


def worker(args):
    i, sid, set_name = args
    t0 = time.time()
    lc, fits, preds, wK = fit_star(sid, seed=1000 + 17 * i)   # no Gaia info used
    out = report(sid, set_name, lc, fits, preds, wK)
    new_top = out["fits"][f"new_K{out['best_K']}"]["top_alias"]
    print(f"[{i + 1:2d}] {sid} done in {time.time() - t0:.0f}s: best K={out['best_K']}, "
          f"old top={out['fits']['old']['top_alias']} new top={new_top}, "
          f"cov95 old/new/const = {preds['old']['cov95']:.2f}/{preds['new']['cov95']:.2f}/"
          f"{preds['const']['cov95']:.2f}", flush=True)
    return out


def main():
    (FIGS / "stars").mkdir(parents=True, exist_ok=True)
    stars = [(int(r["source_id"]), r["set"]) for r in csv.DictReader(open(DATA / "stars.csv"))]
    if len(sys.argv) > 1:                                    # e.g. `python run.py 2` for a smoke test
        stars = stars[:int(sys.argv[1])]
    jobs = [(i, sid, s) for i, (sid, s) in enumerate(stars)]
    with Pool(min(4, os.cpu_count() or 1)) as pool:
        results = pool.map(worker, jobs, chunksize=1)
    with open(HERE / "results.json", "w") as fh:
        json.dump(results, fh, indent=1)
    import summarize
    summarize.main()


if __name__ == "__main__":
    main()
