"""Fourier-series light-curve model with the linear coefficients marginalized.

    y_i = m + sum_k [a_k sin(2 pi k t_i / P) + b_k cos(2 pi k t_i / P)] + eps_i
    eps_i ~ N(0, sigma_i^2 + s^2)

Linear coefficients w = (m, a_1, b_1, ..., a_K, b_K) get a Gaussian prior
N(mu0, diag(var0)).  Integrating w out gives  y ~ N(A mu0, C + A diag(var0) A^T)
with C = diag(sigma^2 + s^2), evaluated with the Woodbury identity so the cost
is O(n p^2), p = 2K + 1.  Everything is vectorized over a batch of (P, s).

A `Prior` may hold several coefficient-prior hypotheses (rows of `var0s`, equal
weight).  The likelihood is then averaged over them, which is exact
marginalization over a discrete hyperparameter, so the sampled posterior is
still over (P, s) only.  Two priors are provided:

  * Prior.flat(K)    -- run 1: every a_k, b_k ~ N(0, 0.5^2)
  * Prior.shrink(K)  -- run 2: a_k, b_k ~ N(0, (sigma_h / k)^2), sigma_h averaged
                        over {0.01, 0.03, 0.1, 0.3}.  Higher harmonics are
                        allowed but must earn their amplitude; sigma_h lets the
                        data choose the overall amplitude scale.

Units: flux is divided by the median training flux, so y ~ 1 and s is a
fractional (relative-flux) jitter.
"""
from dataclasses import dataclass

import numpy as np
from scipy.special import logsumexp

LOG2PI = np.log(2 * np.pi)

# --- priors on (P, s) ---------------------------------------------------------
P_MIN, P_MAX = 0.5, 20.0                  # log-uniform in P
LNP_MIN, LNP_MAX = np.log(P_MIN), np.log(P_MAX)
LNS_MIN, LNS_MAX = np.log(1e-5), np.log(1.0)   # support for ln s
S_SCALE = 0.05                            # half-Cauchy(0, 0.05) on s: weak


def log_prior_lns(lns):
    """log p(ln s) for s ~ half-Cauchy(S_SCALE), including the Jacobian ds/dlns = s."""
    s = np.exp(lns)
    lp = np.log(2 / (np.pi * S_SCALE)) - np.log1p((s / S_SCALE) ** 2) + lns
    return np.where((lns >= LNS_MIN) & (lns <= LNS_MAX), lp, -np.inf)


def log_prior(lnP, lns):
    """Prior on (ln P, ln s): ln P uniform on [ln 0.5, ln 20] (= log-uniform P)."""
    inP = (lnP >= LNP_MIN) & (lnP <= LNP_MAX)
    return np.where(inP, -np.log(LNP_MAX - LNP_MIN), -np.inf) + log_prior_lns(lns)


# --- priors on the linear coefficients ---------------------------------------
@dataclass
class Prior:
    K: int
    mu0: np.ndarray            # (p,)
    var0s: np.ndarray          # (H, p): H equally weighted hypotheses
    name: str

    @staticmethod
    def flat(K, m_sd=1.0, ab_sd=0.5):
        p = 2 * K + 1
        var0 = np.full(p, ab_sd ** 2)
        var0[0] = m_sd ** 2
        return Prior(K, _mu0(p), var0[None, :], f"flat K={K}")

    @staticmethod
    def shrink(K, sigma_h=(0.01, 0.03, 0.1, 0.3), m_sd=1.0):
        p = 2 * K + 1
        k = np.repeat(np.arange(1, K + 1), 2)
        rows = [np.r_[m_sd ** 2, (sh / k) ** 2] for sh in sigma_h]
        return Prior(K, _mu0(p), np.array(rows), f"shrink K={K}")


def _mu0(p):
    mu0 = np.zeros(p)
    mu0[0] = 1.0
    return mu0


# --- design matrix ------------------------------------------------------------
def design(t, freq, K):
    """A[g, i, :] = [1, sin(2pi f t), cos(2pi f t), ..., sin(2pi K f t), cos(...)]."""
    freq = np.atleast_1d(freq)
    A = np.empty((freq.size, t.size, 2 * K + 1))
    A[:, :, 0] = 1.0
    ph = 2 * np.pi * freq[:, None] * t[None, :]
    for k in range(1, K + 1):
        A[:, :, 2 * k - 1] = np.sin(k * ph)
        A[:, :, 2 * k] = np.cos(k * ph)
    return A


# --- marginal likelihood ------------------------------------------------------
def _sufficient(A, y, var, mu0):
    cinv = 1.0 / var                                       # (G,n)
    r = y[None, :] - A @ mu0                               # (G,n)
    Ac = A * cinv[:, :, None]
    AtCA = np.swapaxes(Ac, 1, 2) @ A                       # (G,p,p)
    b = np.einsum("gni,gn->gi", Ac, r)                     # (G,p)
    rCr = (cinv * r * r).sum(1)
    return AtCA, b, rCr, np.log(var).sum(1)


def _ll_per_hyp(A, y, var, prior):
    """(G, H) log marginal likelihood under each coefficient-prior hypothesis."""
    AtCA, b, rCr, logdetC = _sufficient(A, y, var, prior.mu0)
    p = len(prior.mu0)
    out = np.empty((A.shape[0], len(prior.var0s)))
    for h, var0 in enumerate(prior.var0s):
        M = AtCA.copy()
        M[:, np.arange(p), np.arange(p)] += 1.0 / var0
        L = np.linalg.cholesky(M)
        z = np.linalg.solve(L, b[..., None])[..., 0]
        logdet = logdetC + np.log(var0).sum() + 2 * np.log(np.diagonal(L, axis1=1, axis2=2)).sum(1)
        out[:, h] = -0.5 * (y.size * LOG2PI + logdet + rCr - (z * z).sum(1))
    return out


def log_marg_like(t, y, sig, freq, s, prior, per_hyp=False):
    """ln p(y | P = 1/freq, s), coefficients (and hypothesis) marginalized.
    Batched over broadcastable freq and s arrays."""
    freq, s = np.broadcast_arrays(np.asarray(freq, float), np.asarray(s, float))
    shape = freq.shape
    A = design(t, freq.ravel(), prior.K)
    var = sig[None, :] ** 2 + s.ravel()[:, None] ** 2
    llh = _ll_per_hyp(A, y, var, prior)
    if per_hyp:
        return llh
    return (logsumexp(llh, axis=1) - np.log(llh.shape[1])).reshape(shape)


def log_post(t, y, sig, lnP, lns, prior):
    lp = log_prior(lnP, lns)
    out = np.full(np.shape(lnP), -np.inf)
    ok = np.isfinite(lp)
    if ok.any():
        out[ok] = lp[ok] + log_marg_like(t, y, sig, np.exp(-lnP[ok]), np.exp(lns[ok]), prior)
    return out


def coef_posterior(t, y, sig, freq, s, prior, h):
    """Gaussian posterior of w given (P, s, hypothesis h): mean (G,p), cov (G,p,p)."""
    A = design(t, np.atleast_1d(freq), prior.K)
    var = sig[None, :] ** 2 + np.atleast_1d(s)[:, None] ** 2
    AtCA, b, _, _ = _sufficient(A, y, var, prior.mu0)
    p = len(prior.mu0)
    M = AtCA
    M[:, np.arange(p), np.arange(p)] += 1.0 / prior.var0s[h]
    Minv = np.linalg.inv(M)
    return prior.mu0 + np.einsum("gij,gj->gi", Minv, b), Minv


# --- grid reference -----------------------------------------------------------
def grid_posterior(t, y, sig, prior, n_s=100, coarse_every=5, keep_within=30.0, block=2000):
    """Posterior on a (frequency, ln s) grid, in two stages.

    Frequency spacing is 1/(max(30, 6K) T), T = data baseline, so every alias
    peak is resolved even for the K-th harmonic.  Stage 1 evaluates every
    frequency on a coarse ln s grid (every 5th point); stage 2 re-evaluates on
    the full ln s grid only the frequencies whose best coarse cell is within
    `keep_within` nats of the global best.  The rest keep their coarse values
    (their total mass is < n_f * e^-30, i.e. negligible).
    Mass per cell = p(lnP, lns) * |dlnP| * dlns, with |dlnP| = df / f.
    """
    T = t.max() - t.min()
    df = 1.0 / (max(30, 6 * prior.K) * T)
    freqs = np.arange(1 / P_MAX, 1 / P_MIN + df, df)
    lns = np.linspace(LNS_MIN, LNS_MAX, n_s)
    jc = np.arange(0, n_s, coarse_every)
    lp_s = log_prior_lns(lns)

    def evaluate(f, cols):
        out = np.empty((f.size, cols.size))
        for i0 in range(0, f.size, block):
            fb = f[i0:i0 + block]
            for jj, j in enumerate(cols):
                out[i0:i0 + block, jj] = log_marg_like(t, y, sig, fb, np.exp(lns[j]), prior) + lp_s[j]
        return out

    coarse = evaluate(freqs, jc)
    logmass = coarse[:, np.minimum(np.arange(n_s) // coarse_every, jc.size - 1)]
    best = coarse.max(1)
    keep = np.where(best > best.max() - keep_within)[0]
    logmass[keep] = evaluate(freqs[keep], np.arange(n_s))
    logmass += (-np.log(LNP_MAX - LNP_MIN) + np.log(df / freqs))[:, None] + np.log(lns[1] - lns[0])
    mx = logmass.max()
    w = np.exp(logmass - mx)
    Z = w.sum()
    w /= Z
    return dict(freqs=freqs, lns=lns, mass=w, pf=w.sum(1), ps=w.sum(0),
                log_evidence=float(mx + np.log(Z)), n_refined=int(keep.size))


# --- Metropolis-Hastings ------------------------------------------------------
# All proposals are symmetric in (ln P, ln s), so the acceptance ratio is just
# the posterior ratio.  Random-walk moves use a fixed, state-independent mixture
# of step sizes (still symmetric).  Jump moves add +/- ln 2 (period doubling /
# halving) or +/- ln(3/2) (the 2P/3 <-> P alias that trapped chains in run 1),
# sign chosen at random; ln s is left unchanged on jumps.
RW_SCALES_LNP = np.array([3e-4, 3e-3, 3e-2, 0.3, 1.5])
RW_WEIGHTS = np.array([0.30, 0.20, 0.10, 0.10, 0.10])
JUMPS = np.array([np.log(2.0), np.log(1.5)])
JUMP_WEIGHTS = np.array([0.10, 0.10])
MOVE_NAMES = [f"rw_{s:g}" for s in RW_SCALES_LNP] + ["jump_ln2", "jump_ln1.5"]
LNS_STEP = 0.15


def run_mh(t, y, sig, prior, n_chains=16, n_iter=25000, seed=0):
    rng = np.random.default_rng(seed)
    lnP = rng.uniform(LNP_MIN, LNP_MAX, n_chains)            # start from the prior
    lns = np.full(n_chains, np.log(max(np.std(y), 1e-4)))
    lp = log_post(t, y, sig, lnP, lns, prior)
    chain = np.empty((n_iter, n_chains, 2))
    probs = np.r_[RW_WEIGHTS, JUMP_WEIGHTS]
    n_rw = len(RW_SCALES_LNP)
    acc = np.zeros((probs.size, 2))
    for it in range(n_iter):
        kind = rng.choice(probs.size, size=n_chains, p=probs)
        is_jump = kind >= n_rw
        sign = rng.choice([-1.0, 1.0], n_chains)
        dP = np.where(is_jump, sign * JUMPS[np.clip(kind - n_rw, 0, len(JUMPS) - 1)],
                      rng.normal(size=n_chains) * RW_SCALES_LNP[np.minimum(kind, n_rw - 1)])
        ds = np.where(is_jump, 0.0, rng.normal(size=n_chains) * LNS_STEP)
        lnP_new, lns_new = lnP + dP, lns + ds
        lp_new = log_post(t, y, sig, lnP_new, lns_new, prior)
        accept = np.log(rng.uniform(size=n_chains)) < lp_new - lp
        lnP = np.where(accept, lnP_new, lnP)
        lns = np.where(accept, lns_new, lns)
        lp = np.where(accept, lp_new, lp)
        np.add.at(acc[:, 0], kind, accept)
        np.add.at(acc[:, 1], kind, 1)
        chain[it, :, 0], chain[it, :, 1] = lnP, lns
    return dict(chain=chain, acc_by_move=dict(zip(MOVE_NAMES, acc[:, 0] / np.maximum(acc[:, 1], 1))),
                acc_total=float(acc[:, 0].sum() / acc[:, 1].sum()))


# --- modes --------------------------------------------------------------------
def find_modes(freqs, pf, min_mass=1e-4):
    """Split the 1-D frequency marginal into basins (local max to neighbouring
    local minima) and return them sorted by probability mass."""
    d = np.diff(pf)
    peaks = np.where(np.r_[True, d > 0] & np.r_[d <= 0, True])[0]   # local maxima
    bounds = [0]
    for a, b in zip(peaks[:-1], peaks[1:]):
        bounds.append(a + int(np.argmin(pf[a:b + 1])))
    bounds.append(freqs.size)
    modes = []
    for i, pk in enumerate(peaks):
        lo, hi = bounds[i], bounds[i + 1]
        mass = pf[lo:hi].sum()
        if mass >= min_mass:
            modes.append(dict(f_peak=freqs[pk], P_peak=1 / freqs[pk],
                              f_lo=freqs[lo], f_hi=freqs[hi - 1], mass=mass))
    modes.sort(key=lambda m: -m["mass"])
    return modes


def mode_masses_from_samples(f_samples, modes):
    return np.array([np.mean((f_samples >= m["f_lo"]) & (f_samples <= m["f_hi"]))
                     for m in modes])


# --- posterior predictive -----------------------------------------------------
def predictive_components(t_tr, y_tr, s_tr, t_te, s_te, lnP_draws, lns_draws, prior, rng):
    """Per-draw Gaussian predictive for each held-out point.

    For each (P, s) draw, the coefficient-prior hypothesis h is drawn from its
    conditional posterior p(h | P, s, y), then
        y* ~ N(A* wbar_h, diag(A* Cov_h A*^T) + sigma*^2 + s^2).
    Returns mu, var of shape (D, m).
    """
    f, s = np.exp(-lnP_draws), np.exp(lns_draws)
    llh = log_marg_like(t_tr, y_tr, s_tr, f, s, prior, per_hyp=True)       # (D,H)
    ph = np.exp(llh - llh.max(1, keepdims=True))
    ph /= ph.sum(1, keepdims=True)
    h = (rng.uniform(size=(len(f), 1)) > np.cumsum(ph, 1)).sum(1)
    h = np.minimum(h, ph.shape[1] - 1)
    mu = np.empty((len(f), t_te.size))
    var = np.empty_like(mu)
    for hh in np.unique(h):
        sel = h == hh
        mean_w, cov_w = coef_posterior(t_tr, y_tr, s_tr, f[sel], s[sel], prior, hh)
        A = design(t_te, f[sel], prior.K)
        mu[sel] = np.einsum("dmp,dp->dm", A, mean_w)
        var[sel] = (np.einsum("dmp,dpq,dmq->dm", A, cov_w, A)
                    + s_te[None, :] ** 2 + s[sel][:, None] ** 2)
    return mu, var


def score(y_te, mu, var, rng, n_per_draw=25):
    """Quantiles of the predictive mixture (equal-weight over draws), 68/95%
    coverage of the hidden points, and mean log predictive density per point."""
    samp = mu[None] + np.sqrt(var)[None] * rng.normal(size=(n_per_draw,) + mu.shape)
    q = np.quantile(samp.reshape(-1, y_te.size), [0.025, 0.16, 0.5, 0.84, 0.975], axis=0)
    in68 = (y_te >= q[1]) & (y_te <= q[3])
    in95 = (y_te >= q[0]) & (y_te <= q[4])
    ll = -0.5 * (LOG2PI + np.log(var) + (y_te[None] - mu) ** 2 / var)
    lpd = logsumexp(ll, axis=0) - np.log(ll.shape[0])
    return dict(q=q, in68=in68, in95=in95, cov68=float(in68.mean()), cov95=float(in95.mean()),
                lpd_per_point=float(lpd.mean()), lpd_points=lpd)
