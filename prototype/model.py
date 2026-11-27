"""Fourier-series light-curve model with the linear coefficients marginalized.

    y_i = m + sum_k [a_k sin(2 pi k t_i / P) + b_k cos(2 pi k t_i / P)] + eps_i
    eps_i ~ N(0, sigma_i^2 + s^2)

Linear coefficients w = (m, a_1, b_1, ..., a_K, b_K) get a Gaussian prior
N(mu0, Lambda0).  Integrating w out gives  y ~ N(A mu0, C + A Lambda0 A^T)  with
C = diag(sigma^2 + s^2), evaluated with the Woodbury identity so the cost is
O(n p^2) with p = 2K + 1.  Everything is vectorized over a batch of (P, s)
configurations so that the grid and all MH chains run as array operations.

Units: flux is divided by the median training flux, so y ~ 1 and s is a
fractional (relative-flux) jitter.
"""
import numpy as np

LOG2PI = np.log(2 * np.pi)

# --- priors -----------------------------------------------------------------
P_MIN, P_MAX = 0.5, 20.0                  # log-uniform in P
LNP_MIN, LNP_MAX = np.log(P_MIN), np.log(P_MAX)
LNS_MIN, LNS_MAX = np.log(1e-5), np.log(1.0)   # support for ln s
S_SCALE = 0.05                            # half-Cauchy(0, 0.05) on s: weak
M_PRIOR = (1.0, 1.0)                      # mean flux ~ N(1, 1^2)
AB_PRIOR_SD = 0.5                         # each a_k, b_k ~ N(0, 0.5^2)


def coef_prior(K):
    p = 2 * K + 1
    mu0 = np.zeros(p)
    mu0[0] = M_PRIOR[0]
    var0 = np.full(p, AB_PRIOR_SD ** 2)
    var0[0] = M_PRIOR[1] ** 2
    return mu0, var0


def log_prior_lns(lns):
    """log p(ln s) for s ~ half-Cauchy(S_SCALE), including the Jacobian ds/dlns = s."""
    s = np.exp(lns)
    lp = np.log(2 / (np.pi * S_SCALE)) - np.log1p((s / S_SCALE) ** 2) + lns
    return np.where((lns >= LNS_MIN) & (lns <= LNS_MAX), lp, -np.inf)


def log_prior(lnP, lns):
    """Prior on (ln P, ln s): ln P uniform on [ln 0.5, ln 20] (= log-uniform P)."""
    inP = (lnP >= LNP_MIN) & (lnP <= LNP_MAX)
    return np.where(inP, -np.log(LNP_MAX - LNP_MIN), -np.inf) + log_prior_lns(lns)


# --- design matrix ----------------------------------------------------------
def design(t, freq, K):
    """A[g, i, :] = [1, sin(2pi f t), cos(2pi f t), ..., sin(2pi K f t), cos(...)].

    t: (n,), freq: (G,)  ->  (G, n, 2K+1)
    """
    freq = np.atleast_1d(freq)
    A = np.empty((freq.size, t.size, 2 * K + 1))
    A[:, :, 0] = 1.0
    ph = 2 * np.pi * freq[:, None] * t[None, :]
    for k in range(1, K + 1):
        A[:, :, 2 * k - 1] = np.sin(k * ph)
        A[:, :, 2 * k] = np.cos(k * ph)
    return A


# --- marginal likelihood ----------------------------------------------------
def _woodbury(A, y, var, mu0, var0):
    """Shared algebra. A: (G,n,p), var: (G,n) total noise variance."""
    cinv = 1.0 / var                                       # (G,n)
    r = y[None, :] - A @ mu0                               # (G,n)
    M = np.swapaxes(A * cinv[:, :, None], 1, 2) @ A
    M[:, np.arange(len(mu0)), np.arange(len(mu0))] += 1.0 / var0
    b = np.einsum("gni,gn->gi", A, cinv * r)
    L = np.linalg.cholesky(M)
    z = np.linalg.solve(L, b[..., None])[..., 0]           # L z = b
    return r, cinv, M, L, b, z


def log_marg_like(t, y, sig, freq, s, K, mu0=None, var0=None):
    """ln p(y | P = 1/freq, s), linear coefficients marginalized.  Batched over
    broadcastable freq and s arrays (flattened to G configs)."""
    if mu0 is None:
        mu0, var0 = coef_prior(K)
    freq, s = np.broadcast_arrays(np.asarray(freq, float), np.asarray(s, float))
    shape = freq.shape
    freq, s = freq.ravel(), s.ravel()
    A = design(t, freq, K)
    var = sig[None, :] ** 2 + s[:, None] ** 2
    r, cinv, M, L, b, z = _woodbury(A, y, var, mu0, var0)
    logdet = (np.log(var).sum(1) + np.log(var0).sum()
              + 2 * np.log(np.diagonal(L, axis1=1, axis2=2)).sum(1))
    quad = (cinv * r * r).sum(1) - (z * z).sum(1)
    return (-0.5 * (y.size * LOG2PI + logdet + quad)).reshape(shape)


def coef_posterior(t, y, sig, freq, s, K):
    """Gaussian posterior of w given (P, s): returns mean (G,p), cov (G,p,p)."""
    mu0, var0 = coef_prior(K)
    freq, s = np.atleast_1d(freq), np.atleast_1d(s)
    A = design(t, freq, K)
    var = sig[None, :] ** 2 + s[:, None] ** 2
    r, cinv, M, L, b, z = _woodbury(A, y, var, mu0, var0)
    Minv = np.linalg.inv(M)
    mean = mu0 + np.einsum("gij,gj->gi", Minv, b)
    return mean, Minv


def log_post(t, y, sig, lnP, lns, K):
    lp = log_prior(lnP, lns)
    out = np.full(np.shape(lnP), -np.inf)
    ok = np.isfinite(lp)
    if ok.any():
        out[ok] = lp[ok] + log_marg_like(t, y, sig, np.exp(-lnP[ok]), np.exp(lns[ok]), K)
    return out


# --- grid reference ---------------------------------------------------------
def grid_posterior(t, y, sig, K, oversample=30, n_s=160, block=3000):
    """Posterior on a (frequency, ln s) grid.

    Frequency spacing is 1/(oversample * T) with T the data baseline, so every
    alias peak (width ~ 1/(K T)) is resolved.  Returns the grid, the joint
    log-posterior *mass* per cell, and normalized marginals.
    Mass per cell = p(lnP, lns) * |dlnP| * dlns, with |dlnP| = df / f.
    """
    T = t.max() - t.min()
    df = 1.0 / (oversample * T)
    freqs = np.arange(1 / P_MAX, 1 / P_MIN + df, df)
    lns = np.linspace(LNS_MIN, LNS_MAX, n_s)
    dlns = lns[1] - lns[0]
    logmass = np.empty((freqs.size, n_s))
    lp_s = log_prior_lns(lns)
    for i0 in range(0, freqs.size, block):
        f = freqs[i0:i0 + block]
        for j, ls in enumerate(lns):
            logmass[i0:i0 + block, j] = log_marg_like(t, y, sig, f, np.exp(ls), K) + lp_s[j]
    logmass += (-np.log(LNP_MAX - LNP_MIN) + np.log(df / freqs))[:, None] + np.log(dlns)
    mx = logmass.max()
    w = np.exp(logmass - mx)
    Z = w.sum()
    w /= Z
    return dict(freqs=freqs, lns=lns, mass=w, pf=w.sum(1), ps=w.sum(0),
                log_evidence=mx + np.log(Z))


# --- Metropolis-Hastings ----------------------------------------------------
# All proposals are symmetric in (ln P, ln s), so the acceptance ratio is just
# the posterior ratio.  Gaussian random-walk moves use a fixed, state-independent
# mixture of step sizes (still symmetric): small steps explore inside a narrow
# alias peak, large ones let a chain find other peaks.  The +/- ln 2 move is a
# period-doubling/halving jump, chosen with sign +/- at random.
RW_SCALES_LNP = np.array([3e-4, 3e-3, 3e-2, 0.3, 1.5])
RW_WEIGHTS = np.array([0.30, 0.20, 0.10, 0.10, 0.10])
JUMP_WEIGHT = 0.20                          # remaining probability mass
LNS_STEP = 0.15


def run_mh(t, y, sig, K, n_chains=24, n_iter=40000, seed=0):
    rng = np.random.default_rng(seed)
    lnP = rng.uniform(LNP_MIN, LNP_MAX, n_chains)            # start from the prior
    lns = np.full(n_chains, np.log(max(np.std(y), 1e-4)))
    lp = log_post(t, y, sig, lnP, lns, K)
    chain = np.empty((n_iter, n_chains, 2))
    lpc = np.empty((n_iter, n_chains))
    kinds = np.empty((n_iter, n_chains), dtype=np.int8)
    acc = np.zeros((len(RW_SCALES_LNP) + 1, 2))              # accepted, proposed
    probs = np.append(RW_WEIGHTS, JUMP_WEIGHT)
    for it in range(n_iter):
        kind = rng.choice(probs.size, size=n_chains, p=probs)
        is_jump = kind == len(RW_SCALES_LNP)
        dP = np.where(is_jump, rng.choice([-1.0, 1.0], n_chains) * np.log(2),
                      rng.normal(size=n_chains) * RW_SCALES_LNP[np.minimum(kind, len(RW_SCALES_LNP) - 1)])
        ds = np.where(is_jump, 0.0, rng.normal(size=n_chains) * LNS_STEP)
        lnP_new, lns_new = lnP + dP, lns + ds
        lp_new = log_post(t, y, sig, lnP_new, lns_new, K)
        accept = np.log(rng.uniform(size=n_chains)) < lp_new - lp
        lnP = np.where(accept, lnP_new, lnP)
        lns = np.where(accept, lns_new, lns)
        lp = np.where(accept, lp_new, lp)
        np.add.at(acc[:, 0], kind, accept)
        np.add.at(acc[:, 1], kind, 1)
        chain[it, :, 0], chain[it, :, 1], lpc[it] = lnP, lns, lp
        kinds[it] = kind
    return dict(chain=chain, logpost=lpc, acc_by_move=acc[:, 0] / np.maximum(acc[:, 1], 1),
                acc_total=acc[:, 0].sum() / acc[:, 1].sum())


# --- modes ------------------------------------------------------------------
def find_modes(freqs, pf, min_mass=1e-4):
    """Split the 1-D frequency marginal into basins (local max to neighbouring
    local minima) and return them sorted by probability mass."""
    d = np.diff(pf)
    peaks = np.where(np.r_[True, d > 0] & np.r_[d <= 0, True])[0]   # local maxima
    # boundaries between consecutive peaks at the minimum of pf between them
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


# --- posterior predictive ---------------------------------------------------
def predictive(t_tr, y_tr, s_tr, t_te, s_te, lnP_draws, lns_draws, K,
               n_per_draw=25, seed=1):
    """Posterior predictive for held-out points as a mixture over (P, s) draws.

    For each draw: y* ~ N(A* wbar, A* Cov_w A*^T + sigma*^2 + s^2) (diagonal used,
    points are scored one at a time).  Returns per-point quantiles, the exact
    mixture log predictive density, and Monte Carlo predictive samples.
    """
    rng = np.random.default_rng(seed)
    f = np.exp(-lnP_draws)
    s = np.exp(lns_draws)
    mean_w, cov_w = coef_posterior(t_tr, y_tr, s_tr, f, s, K)
    A = design(t_te, f, K)                                  # (D, m, p)
    mu = np.einsum("dmp,dp->dm", A, mean_w)
    var = (np.einsum("dmp,dpq,dmq->dm", A, cov_w, A)
           + s_te[None, :] ** 2 + s[:, None] ** 2)
    samp = mu[None] + np.sqrt(var)[None] * rng.normal(size=(n_per_draw,) + mu.shape)
    samp = samp.reshape(-1, t_te.size)
    q = np.quantile(samp, [0.025, 0.16, 0.5, 0.84, 0.975], axis=0)
    return dict(mu=mu, var=var, q=q)


def coverage_and_lpd(y_te, mu, var, q):
    in68 = (y_te >= q[1]) & (y_te <= q[3])
    in95 = (y_te >= q[0]) & (y_te <= q[4])
    # mixture log density per held-out point, averaged over draws
    ll = -0.5 * (LOG2PI + np.log(var) + (y_te[None] - mu) ** 2 / var)
    m = ll.max(0)
    lpd = m + np.log(np.mean(np.exp(ll - m), axis=0))
    return dict(cov68=float(in68.mean()), cov95=float(in95.mean()),
                lpd_per_point=float(lpd.mean()), in68=in68, in95=in95)
