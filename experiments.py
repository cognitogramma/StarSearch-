"""Run both regimes, write figures to figs/ and numbers to results.json."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from stellar_mh import (simulate_light_curve, log_posterior, grid_posterior,
                        metropolis_hastings, split_rhat, effective_sample_size,
                        mode_masses)

SEED = 7
F_TRUE = 1 / 2.7            # true period 2.7 days
F_MIN, F_MAX = 0.02, 1.5    # prior range: periods from 0.67 to 50 days
STARTS = [0.1, 0.5, 0.9, 1.4]

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#1b1b1b", "#5c5b57", "#e4e3df"
CHAIN_COLORS = [BLUE, ORANGE, AQUA, YELLOW]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 13, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "savefig.dpi": 200, "savefig.bbox": "tight",
})

rng = np.random.default_rng(SEED)

# ---------------- data ----------------
# Regime I: strong signal, continuous coverage (like a space telescope)
t1 = np.sort(rng.uniform(0, 90, 120)); s1 = np.full(120, 0.3)
y1 = simulate_light_curve(t1, F_TRUE, 1.0, 0.8, 10.0, s1, rng)
# Regime II: weak signal, ground-based (one short visit per night, 40 nights)
nights = np.sort(rng.choice(90, 40, replace=False))
t2 = nights + rng.uniform(0, 0.25, 40); s2 = np.full(40, 0.5)
y2 = simulate_light_curve(t2, F_TRUE, 0.45, 0.8, 10.0, s2, rng)
REG = {"I": (t1, y1, s1), "II": (t2, y2, s2)}
np.savetxt("data/regime_I.csv", np.column_stack([t1, y1, s1]), delimiter=",",
           header="t_days,brightness,sigma", comments="", fmt="%.5f")
np.savetxt("data/regime_II.csv", np.column_stack([t2, y2, s2]), delimiter=",",
           header="t_days,brightness,sigma", comments="", fmt="%.5f")

fg = np.linspace(F_MIN, F_MAX, 80000)
post = {k: grid_posterior(fg, *v, F_MIN, F_MAX) for k, v in REG.items()}
results = {"f_true": F_TRUE, "P_true": 1 / F_TRUE}


def peak_sd(p, center, half=0.01):
    m = (fg > center - half) & (fg < center + half)
    w = p[m] / p[m].sum()
    mu = np.sum(w * fg[m])
    return np.sqrt(np.sum(w * (fg[m] - mu) ** 2))


# ---------------- figure: raw light curves ----------------
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
for a, (k, (t, y, s)), c, title in zip(ax, REG.items(), [BLUE, ORANGE],
        ["Regime I: 120 points, continuous coverage", "Regime II: 40 nightly visits, weak signal"]):
    a.errorbar(t, y, yerr=s, fmt="o", ms=4.5, color=c, ecolor=GRID, elinewidth=1.2)
    a.set_title(title); a.set_xlabel("time (days)"); a.set_ylabel("brightness")
fig.savefig("figs/lightcurves.png"); plt.close(fig)

# ---------------- figure: phase-folded ----------------
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
for a, (k, (t, y, s)), c in zip(ax, REG.items(), [BLUE, ORANGE]):
    ph = (t * F_TRUE) % 1.0
    a.errorbar(np.r_[ph, ph + 1], np.r_[y, y], yerr=np.r_[s, s], fmt="o", ms=4.5,
               color=c, ecolor=GRID, elinewidth=1.2)
    a.set_title(f"Regime {k} folded at P = 2.7 d"); a.set_xlabel("phase (cycles)")
    a.set_ylabel("brightness")
fig.savefig("figs/folded.png"); plt.close(fig)

# ---------------- figure: spectral window (why aliases appear) ----------------
fw = np.linspace(0.0, 2.5, 6000)
fig, ax = plt.subplots(1, 2, figsize=(13, 3.8), sharey=True)
for a, (k, (t, y, s)), c in zip(ax, REG.items(), [BLUE, ORANGE]):
    W = np.abs(np.exp(-2j * np.pi * np.outer(fw, t)).sum(axis=1)) ** 2 / len(t) ** 2
    a.plot(fw, W, color=c, lw=1.6)
    a.set_title(f"Regime {k}: sampling pattern alone"); a.set_xlabel("frequency (cycles/day)")
ax[0].set_ylabel("spectral window")
ax[1].annotate("echo at 1 cycle/day\n(one visit per night)", xy=(1.0, 0.85), xytext=(1.35, 0.7),
               arrowprops=dict(arrowstyle="->", color=INK), color=INK)
fig.savefig("figs/window.png"); plt.close(fig)

# ---------------- figure: grid posteriors ----------------
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
ax[0].plot(fg, post["I"], color=BLUE, lw=1.6)
ax[0].set_title("Regime I: one needle-thin peak"); ax[0].set_xlabel("frequency f (cycles/day)")
ax[0].set_ylabel("p(f | data)")
ins = ax[0].inset_axes([0.5, 0.35, 0.45, 0.55])
m = np.abs(fg - F_TRUE) < 0.004
ins.plot(fg[m], post["I"][m], color=BLUE, lw=1.6); ins.set_title("zoomed in", fontsize=11)
ins.tick_params(labelsize=9)
ax[1].plot(fg, post["II"], color=ORANGE, lw=1.6)
ax[1].set_title("Regime II: three competing peaks"); ax[1].set_xlabel("frequency f (cycles/day)")
for f0, lab in [(F_TRUE, "true\n2.70 d"), (1 - F_TRUE, "1 − f\n1.59 d"), (1 + F_TRUE, "1 + f\n0.73 d")]:
    i = np.argmin(np.abs(fg - f0) + 1e9 * (np.abs(fg - f0) > 0.01) - post["II"] * 1e-9)
    j = np.argmax(np.where(np.abs(fg - f0) < 0.01, post["II"], -1))
    ax[1].annotate(lab, xy=(fg[j], post["II"][j]), xytext=(fg[j] + 0.06, post["II"][j] * 0.9),
                   fontsize=11, color=INK)
fig.savefig("figs/posteriors.png"); plt.close(fig)

# ---------------- experiments ----------------
def run_chains(k, step, p_jump, n, burn):
    t, y, s = REG[k]
    lt = lambda f: log_posterior(f, t, y, s, F_MIN, F_MAX)
    full, accs = [], []
    for f0 in STARTS:
        c, a = metropolis_hastings(lt, f0, n, step, rng, p_jump=p_jump, f_min=F_MIN, f_max=F_MAX)
        full.append(c); accs.append(a)
    full = np.array(full)
    kept = full[:, burn:]
    return full, kept, {
        "acceptance": float(np.mean(accs)),
        "rhat": float(split_rhat(kept)),
        "ess_total": float(sum(effective_sample_size(c) for c in kept)),
        "n_kept": int(kept.size),
        "means_P": [float(1 / c.mean()) for c in kept],
    }

sd_I = peak_sd(post["I"], F_TRUE); sd_II = peak_sd(post["II"], F_TRUE, 0.02)
step_I, step_II = 2.4 * sd_I, 2.4 * sd_II
results["peak_sd_I"], results["peak_sd_II"] = sd_I, sd_II
results["step_I"], results["step_II"] = step_I, step_II

N, BURN = 40000, 5000
rwI_full, rwI, results["I_rw"] = run_chains("I", step_I, 0.0, N, BURN)
mxI_full, mxI, results["I_mix"] = run_chains("I", step_I, 0.05, N, BURN)
N2, BURN2 = 120000, 10000
rwII_full, rwII, results["II_rw"] = run_chains("II", step_II, 0.0, N2, BURN2)
mxII_full, mxII, results["II_mix"] = run_chains("II", step_II, 0.05, N2, BURN2)

# mode masses in Regime II
win = [(F_TRUE - 0.02, F_TRUE + 0.02), (1 - F_TRUE - 0.02, 1 - F_TRUE + 0.02),
       (1 + F_TRUE - 0.02, 1 + F_TRUE + 0.02)]
results["II_masses"] = {
    "grid": mode_masses(post["II"], win, f_grid=fg).tolist(),
    "mix": mode_masses(mxII.ravel(), win).tolist(),
    "rw_per_chain": [mode_masses(c, win).tolist() for c in rwII],
}
results["I_mass_true_grid"] = float(mode_masses(post["I"], [win[0]], f_grid=fg)[0])
# posterior summaries (period) from mixture chains in regime I
P_I = 1 / mxI.ravel()
results["I_P_mean"], results["I_P_sd"] = float(P_I.mean()), float(P_I.std())
results["I_P_q"] = np.percentile(P_I, [2.5, 50, 97.5]).tolist()


def traces(full_a, full_b, title_a, title_b, fname, ylim=(F_MIN, F_MAX)):
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    for a, full, title in [(ax[0], full_a, title_a), (ax[1], full_b, title_b)]:
        for c, col, f0 in zip(full, CHAIN_COLORS, STARTS):
            it = np.arange(len(c))[::20]
            a.scatter(it, c[::20], s=2.5, color=col, alpha=0.6, linewidths=0, label=f"start f = {f0}")
        a.axhline(F_TRUE, color=INK, lw=1, ls="--")
        a.set_title(title); a.set_xlabel("iteration (thousands)")
        a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:g}")); a.set_ylim(*ylim)
    ax[0].set_ylabel("frequency f"); fig.legend(*ax[0].get_legend_handles_labels(), loc="lower center", ncol=4, fontsize=11,
               markerscale=5, bbox_to_anchor=(0.5, -0.12))
    ax[0].text(0.01, F_TRUE + 0.03, "true f", color=INK, fontsize=10, transform=ax[0].get_yaxis_transform())
    fig.savefig(fname); plt.close(fig)

traces(rwI_full, mxI_full, "Random walk only", "Random walk + 5% global jumps", "figs/regI_traces.png")
traces(rwII_full, mxII_full, "Random walk only", "Random walk + 5% global jumps", "figs/regII_traces.png")

# histogram vs grid, regime II: one zoomed panel per peak
fig, ax = plt.subplots(1, 3, figsize=(9, 4.6), sharey=True)
pooled = mxII.ravel()
bw = 0.0008
for a, (lo, hi), name in zip(ax, [win[0], win[2], win[1]], ["true f (2.70 d)", "1 + f (0.73 d)", "1 − f (1.59 d)"]):
    a.hist(pooled[(pooled > lo) & (pooled < hi)], bins=np.arange(lo, hi + bw, bw),
           weights=np.full(np.sum((pooled > lo) & (pooled < hi)), 1 / (len(pooled) * bw)),
           color=ORANGE, alpha=0.75, label="MH samples")
    m = (fg > lo) & (fg < hi)
    a.plot(fg[m], post["II"][m], color=INK, lw=1.6, label="exact (grid)")
    a.set_title(name, fontsize=13); a.set_xlim(lo + 0.01, hi - 0.01)
    a.tick_params(axis="x", labelsize=10); a.set_xlabel("f (cycles/day)", fontsize=11)
ax[0].set_ylabel("density")
fig.legend(*ax[0].get_legend_handles_labels(), loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.07))
fig.savefig("figs/regII_hist.png"); plt.close(fig)

# step-size study, regime I, started at the peak
t, y, s = REG["I"]
lt = lambda f: log_posterior(f, t, y, s, F_MIN, F_MAX)
mult = [0.1, 0.3, 1, 2.4, 6, 20, 60]
study = []
for mlt in mult:
    c, a = metropolis_hastings(lt, F_TRUE, 20000, mlt * sd_I, rng)
    study.append({"mult": mlt, "acceptance": a, "ess_per_1000": effective_sample_size(c) / 20})
results["step_study"] = study

json.dump(results, open("results.json", "w"), indent=2)
print(json.dumps(results, indent=2))
