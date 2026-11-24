"""
Recovering a variable star's period with Metropolis-Hastings.

Everything is written out by hand (numpy only) so each line can be matched
to a line of mathematics on the slides.

Model (slide: "Observation model")
    y_i = a sin(2 pi f t_i) + b cos(2 pi f t_i) + c + eps_i,   eps_i ~ N(0, sigma_i^2)

    f      : frequency (cycles/day), the parameter we care about. Period P = 1/f.
    a, b, c: amplitude/phase/offset ("nuisance" parameters). They enter LINEARLY,
             so they can be integrated out exactly (slide: "Marginalization").

Posterior over f alone (flat priors on a, b, c; uniform prior on f in [f_min, f_max]):
    log p(f | y) = const - 1/2 chi2_min(f) - 1/2 log det(X^T W X)
"""
import numpy as np

TWO_PI = 2.0 * np.pi


# --------------------------------------------------------------------------
# 1. Data
# --------------------------------------------------------------------------
def simulate_light_curve(t, f_true, amp, phase, offset, sigma, rng):
    """Noisy sinusoid observed at times t."""
    signal = amp * np.sin(TWO_PI * f_true * t + phase) + offset
    return signal + rng.normal(0.0, sigma, size=t.shape)


# --------------------------------------------------------------------------
# 2. Log posterior of the frequency (a, b, c integrated out)
# --------------------------------------------------------------------------
def design_matrix(t, f):
    """Columns: sin, cos, constant.  y = X @ [a, b, c] + noise."""
    w = TWO_PI * f * t
    return np.column_stack([np.sin(w), np.cos(w), np.ones_like(t)])


def log_posterior(f, t, y, sigma, f_min, f_max):
    """log p(f | y) up to an additive constant.

    Derivation (appendix slide): with W = diag(1/sigma_i^2),
        chi2(theta) = (y - X theta)^T W (y - X theta)
                    = chi2_min + (theta - theta_hat)^T (X^T W X) (theta - theta_hat)
    Integrating exp(-chi2/2) over theta (a Gaussian integral) gives
        (2 pi)^{3/2} det(X^T W X)^{-1/2} exp(-chi2_min / 2).
    """
    if f < f_min or f > f_max:          # uniform prior: zero density outside
        return -np.inf
    X = design_matrix(t, f)
    w = 1.0 / sigma**2
    XtWX = X.T @ (X * w[:, None])       # 3x3 matrix
    XtWy = X.T @ (w * y)
    theta_hat = np.linalg.solve(XtWX, XtWy)          # weighted least squares fit
    resid = y - X @ theta_hat
    chi2_min = np.sum(w * resid**2)
    sign, logdet = np.linalg.slogdet(XtWX)
    return -0.5 * chi2_min - 0.5 * logdet


def grid_posterior(f_grid, t, y, sigma, f_min, f_max):
    """Ground truth: evaluate the 1D posterior on a fine grid and normalize."""
    logp = np.array([log_posterior(f, t, y, sigma, f_min, f_max) for f in f_grid])
    p = np.exp(logp - logp.max())
    p /= np.trapezoid(p, f_grid)
    return p


# --------------------------------------------------------------------------
# 3. Metropolis-Hastings
# --------------------------------------------------------------------------
def metropolis_hastings(log_target, f0, n_steps, step, rng,
                        p_jump=0.0, f_min=None, f_max=None):
    """Random-walk MH, optionally mixed with 'global jump' proposals.

    Proposal kernel q(f' | f):
      with prob 1 - p_jump : f' = f + step * N(0, 1)      (local random walk)
      with prob p_jump     : f' ~ Uniform(f_min, f_max)   (global jump)
    Both pieces are symmetric (q(f'|f) = q(f|f')), and so is their mixture, so the
    Hastings correction cancels and
        alpha(f -> f') = min(1, pi(f') / pi(f)).
    """
    chain = np.empty(n_steps)
    f, logp = f0, log_target(f0)
    n_accept = 0
    for k in range(n_steps):
        if p_jump > 0 and rng.random() < p_jump:
            f_prop = rng.uniform(f_min, f_max)
        else:
            f_prop = f + step * rng.normal()
        logp_prop = log_target(f_prop)
        # accept with probability min(1, exp(logp_prop - logp)); compare in log space
        if np.log(rng.random()) < logp_prop - logp:
            f, logp = f_prop, logp_prop
            n_accept += 1
        chain[k] = f                     # a rejection repeats the current state
    return chain, n_accept / n_steps


# --------------------------------------------------------------------------
# 4. Diagnostics
# --------------------------------------------------------------------------
def split_rhat(chains):
    """Gelman-Rubin R-hat on split chains. ~1.00 means chains agree; >1.01 is a warning."""
    half = chains.shape[1] // 2
    parts = np.vstack([chains[:, :half], chains[:, half:2 * half]])
    m, n = parts.shape
    W = parts.var(axis=1, ddof=1).mean()
    B = n * parts.mean(axis=1).var(ddof=1)
    var_hat = (n - 1) / n * W + B / n
    return np.sqrt(var_hat / W)


def effective_sample_size(x):
    """ESS = n / (1 + 2 sum of autocorrelations), summed until they first go negative."""
    x = x - x.mean()
    n = len(x)
    if np.allclose(x, 0):
        return 1.0
    acf = np.correlate(x, x, mode="full")[n - 1:] / (x.var() * n)
    s = 0.0
    for lag in range(1, n):
        if acf[lag] < 0:
            break
        s += acf[lag]
    return n / (1 + 2 * s)


def mode_masses(samples_or_grid, windows, weights=None, f_grid=None):
    """Probability in each window [lo, hi], from samples or from a gridded density."""
    out = []
    for lo, hi in windows:
        if f_grid is not None:
            m = (f_grid >= lo) & (f_grid <= hi)
            out.append(np.trapezoid(samples_or_grid[m], f_grid[m]))
        else:
            out.append(np.mean((samples_or_grid >= lo) & (samples_or_grid <= hi)))
    return np.array(out)
