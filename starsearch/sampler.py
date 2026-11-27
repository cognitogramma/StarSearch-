"""Periodogram-guided Metropolis-Hastings over frequency.

Two move types, chosen at random each iteration. Each one is a valid MH kernel
for the posterior pi(f) on its own, so their random mixture is too.

1. Local random walk:      f' = f + s * N(0, 1).  Symmetric, so
                           alpha = min(1, pi(f') / pi(f)).
2. Independence proposal:  f' ~ g, where g is a mixture of Gaussians centred on
                           candidate peaks found by a fast periodogram (plus a
                           uniform floor).  NOT symmetric, so the Hastings
                           correction is needed:
                           alpha = min(1, pi(f') g(f) / (pi(f) g(f'))).

Move 2 is the "smart jump" from the slides: it lets the chain move between
alias peaks, which a random walk almost never does.
"""
import numpy as np
from astropy.timeseries import LombScargle

SIDEREAL = 1.0027379  # cycles/day: ground-based aliases sit at f +- k * this


# ---------------------------------------------------------------------------
# candidate peaks
# ---------------------------------------------------------------------------
def periodogram_peaks(lc, n_peaks=6, oversample=5):
    T = lc.T
    df = 1.0 / (oversample * T)
    freq = np.arange(lc.f_min, lc.f_max, df)
    power = LombScargle(lc.t, lc.y, lc.sigma).power(freq, method="fast")
    is_peak = np.r_[False, (power[1:-1] > power[:-2]) & (power[1:-1] >= power[2:]), False]
    idx = np.where(is_peak)[0]
    idx = idx[np.argsort(power[idx])[::-1]]
    chosen = []
    for i in idx:
        if all(abs(freq[i] - freq[j]) > 2.0 / T for j in chosen):
            chosen.append(i)
        if len(chosen) == n_peaks:
            break
    return freq[chosen], power[chosen]


def expand_candidates(lc, peaks):
    """Add the usual suspects: harmonics (f/2, 2f) and daily aliases (|f +- k|)."""
    cands = []
    for f in peaks:
        cands += [f, f / 2, 2 * f]
        for k in (1, 2):
            cands += [abs(f - k * SIDEREAL), f + k * SIDEREAL]
    cands = [c for c in cands if lc.f_min <= c <= lc.f_max]
    out = []
    for c in sorted(cands):
        if not out or c - out[-1] > 1.0 / lc.T:
            out.append(c)
    return np.array(out)


def refine(lc, cands, half_width=1.5, n=31):
    """Exact log-likelihood on a small grid around each candidate.
    Returns refined centres, local s.d., and local log-mass (a quadrature
    estimate of how much posterior probability each peak holds)."""
    T = lc.T
    mus, sds, logm = [], [], []
    for c in cands:
        g = np.linspace(max(lc.f_min, c - half_width / T), min(lc.f_max, c + half_width / T), n)
        ll = lc.log_like_many(g)
        mx = ll.max()
        p = np.exp(ll - mx)
        mass = np.trapezoid(p, g)
        mu = np.sum(p * g) / p.sum()
        sd = np.sqrt(max(np.sum(p * (g - mu) ** 2) / p.sum(), (0.02 / T) ** 2))
        mus.append(g[np.argmax(ll)]); sds.append(sd); logm.append(mx + np.log(mass + 1e-300))
    return np.array(mus), np.array(sds), np.array(logm)


# ---------------------------------------------------------------------------
# Metropolis-Hastings
# ---------------------------------------------------------------------------
class Proposal:
    """g(f) = (1 - u) * sum_j w_j N(f; mu_j, sd_j^2) + u * Uniform(f_min, f_max)."""

    def __init__(self, mus, sds, logm, f_min, f_max, temper=0.3, u=0.05):
        w = np.exp(temper * (logm - logm.max()))   # flattened weights: still visit small peaks
        self.w = w / w.sum()
        self.mus, self.sds = mus, sds * 1.5          # a bit wider than the peaks
        self.f_min, self.f_max, self.u = f_min, f_max, u

    def sample(self, rng):
        if rng.random() < self.u:
            return rng.uniform(self.f_min, self.f_max)
        j = rng.choice(len(self.w), p=self.w)
        return rng.normal(self.mus[j], self.sds[j])

    def logpdf(self, f):
        comp = self.w * np.exp(-0.5 * ((f - self.mus) / self.sds) ** 2) / (np.sqrt(2 * np.pi) * self.sds)
        return np.log((1 - self.u) * comp.sum() + self.u / (self.f_max - self.f_min))


def mh_chain(lc, f0, n_steps, step, prop, rng, p_ind=0.3):
    chain = np.empty(n_steps)
    f, lp = f0, lc.log_post(f0)
    acc = {"rw": [0, 0], "ind": [0, 0]}
    for k in range(n_steps):
        if rng.random() < p_ind:
            fp = prop.sample(rng)
            lpp = lc.log_post(fp)
            log_alpha = lpp - lp + prop.logpdf(f) - prop.logpdf(fp)   # Hastings correction
            kind = "ind"
        else:
            fp = f + step * rng.normal()
            lpp = lc.log_post(fp)
            log_alpha = lpp - lp
            kind = "rw"
        acc[kind][1] += 1
        if np.log(rng.random()) < log_alpha:
            f, lp = fp, lpp
            acc[kind][0] += 1
        chain[k] = f
    rates = {k: (a / n if n else np.nan) for k, (a, n) in acc.items()}
    return chain, rates


def split_rhat(chains):
    half = chains.shape[1] // 2
    parts = np.vstack([chains[:, :half], chains[:, half:2 * half]])
    m, n = parts.shape
    W = parts.var(axis=1, ddof=1).mean()
    B = n * parts.mean(axis=1).var(ddof=1)
    if W <= 0:
        return np.inf if B > 0 else 1.0
    return float(np.sqrt(((n - 1) / n * W + B / n) / W))


def modes_from_samples(samples, T, top=3):
    """Cluster samples into peaks (gaps wider than 1/T split clusters)."""
    s = np.sort(samples)
    cuts = np.where(np.diff(s) > 1.0 / T)[0]
    groups = np.split(s, cuts + 1)
    groups.sort(key=len, reverse=True)
    out = []
    for g in groups[:top]:
        out.append((float(np.median(g)), float(len(g) / len(s)), float(np.std(g))))
    return out


# ---------------------------------------------------------------------------
# one star, end to end
# ---------------------------------------------------------------------------
def analyse(lc, rng, n_chains=3, n_steps=2000, burn=400):
    peaks, power = periodogram_peaks(lc)
    if len(peaks) == 0:
        return None
    lc.calibrate_noise(peaks[0])
    cands = expand_candidates(lc, peaks)
    mus, sds, logm = refine(lc, cands)
    prop = Proposal(mus, sds, logm, lc.f_min, lc.f_max)
    step = 2.4 * np.median(sds)

    order = np.argsort(logm)[::-1]
    starts = [mus[order[0]], mus[rng.integers(len(mus))], rng.uniform(lc.f_min, lc.f_max)]
    chains, rates = [], []
    for c in range(n_chains):
        ch, r = mh_chain(lc, starts[c % len(starts)], n_steps, step, prop, rng)
        chains.append(ch[burn:]); rates.append(r)
    chains = np.array(chains)
    pooled = chains.ravel()
    modes = modes_from_samples(pooled, lc.T)
    # per-chain probability of the overall top mode: do the chains agree?
    f1 = modes[0][0]
    per_chain_p1 = [np.mean(np.abs(c - f1) < 1.0 / lc.T) for c in chains]

    # quadrature reference over the candidate peaks
    qm = np.exp(logm - logm.max()); qm /= qm.sum()
    q_top = mus[order[0]]

    # detection: Bayes factor periodic vs constant (approx. integral over f)
    logZ_per = logm.max() + np.log(np.exp(logm - logm.max()).sum()) - np.log(lc.f_max - lc.f_min)
    log_bf = logZ_per - lc.logZ_const

    return {
        "f1": f1, "p1": modes[0][1], "sd1": modes[0][2],
        "f2": modes[1][0] if len(modes) > 1 else np.nan, "p2": modes[1][1] if len(modes) > 1 else 0.0,
        "f3": modes[2][0] if len(modes) > 2 else np.nan, "p3": modes[2][1] if len(modes) > 2 else 0.0,
        "rhat": split_rhat(chains), "p1_spread": float(np.ptp(per_chain_p1)),
        "acc_rw": float(np.mean([r["rw"] for r in rates])),
        "acc_ind": float(np.mean([r["ind"] for r in rates])),
        "f_quad": float(q_top), "p_quad": float(qm[order[0]]),
        "f_ls": float(peaks[0]), "ls_power": float(power[0]),
        "log_bf": float(log_bf), "noise_scale": float(lc.s),
        "n_cands": int(len(mus)),
    }
