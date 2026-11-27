"""Harmonic light-curve model with the linear parameters integrated out exactly.

Model at frequency f with K harmonics:
    y_i = c + sum_k [ a_k sin(2 pi k f t_i) + b_k cos(2 pi k f t_i) ] + eps_i,
    eps_i ~ N(0, (s * sigma_i)^2)

Priors: c flat; every a_k, b_k ~ N(0, tau^2) (a proper prior, which is what makes
Bayes factors against a constant-brightness model well defined).

Because the model is linear in theta = (a, b, c), the marginal likelihood
    Z(f) = integral p(y | f, theta) p(theta) d theta
is a Gaussian integral:
    log Z(f) = const - 1/2 y'Wy + 1/2 r' A^{-1} r - 1/2 log det A + (log det Lambda_h)/2
with A = X'WX + Lambda (Lambda = prior precision, 0 for the offset) and r = X'Wy.
The posterior over frequency is p(f | y) ∝ Z(f) p(f).
"""
import numpy as np

TWO_PI = 2.0 * np.pi


def design(t, f, K, G=None):
    """Columns: sin(kwt), cos(kwt) for k = 1..K, then one offset column per group
    (G is an (N, n_groups) indicator matrix; default: a single constant)."""
    w = TWO_PI * f * t
    cols = []
    for k in range(1, K + 1):
        cols.append(np.sin(k * w))
        cols.append(np.cos(k * w))
    G = np.ones((len(t), 1)) if G is None else G
    return np.column_stack(cols + [G])


class LightCurve:
    """Pre-computes everything that does not depend on frequency."""

    def __init__(self, t, y, sigma, K=2, tau=1.0, f_min=None, f_max=10.0, groups=None):
        """groups: optional integer label per point (e.g. ZTF field/CCD). Each group
        gets its own zero-point offset, also integrated out exactly."""
        self.t = np.asarray(t, float) - np.min(t)
        g = np.zeros(len(self.t), int) if groups is None else np.unique(groups, return_inverse=True)[1]
        self.G = np.eye(g.max() + 1)[g]
        self.y = np.asarray(y, float)
        self.sigma = np.asarray(sigma, float)
        self.K, self.tau = K, tau
        self.T = self.t.max()
        self.f_min = f_min if f_min is not None else 2.0 / self.T
        self.f_max = f_max
        self.set_noise_scale(1.0)

    def set_noise_scale(self, s):
        self.s = s
        self.w = 1.0 / (s * self.sigma) ** 2
        p = 2 * self.K + self.G.shape[1]
        self.Lam = np.zeros((p, p))
        self.Lam[np.arange(2 * self.K), np.arange(2 * self.K)] = 1.0 / self.tau ** 2
        # constant model (offsets only) for Bayes factors
        sw = self.G.T @ self.w                       # per-group sum of weights
        swy = self.G.T @ (self.w * self.y)
        self.yWy = (self.w * self.y ** 2).sum()
        self.logZ_const = -0.5 * self.yWy + 0.5 * np.sum(swy ** 2 / sw) - 0.5 * np.sum(np.log(sw))
        self.logdetLam_h = 2 * self.K * np.log(1.0 / self.tau ** 2)

    def log_like(self, f):
        """log Z(f) (up to a constant shared with logZ_const). Scalar f."""
        X = design(self.t, f, self.K, self.G)
        XW = X * self.w[:, None]
        A = X.T @ XW + self.Lam
        r = XW.T @ self.y
        L = np.linalg.cholesky(A)
        z = np.linalg.solve(L, r)
        return (-0.5 * self.yWy + 0.5 * z @ z - np.log(np.diag(L)).sum()
                + 0.5 * self.logdetLam_h)

    def log_like_many(self, freqs, chunk=512):
        """Vectorised log Z(f) for an array of frequencies."""
        freqs = np.asarray(freqs, float)
        out = np.empty(len(freqs))
        for s0 in range(0, len(freqs), chunk):
            fs = freqs[s0:s0 + chunk]
            w = TWO_PI * np.outer(fs, self.t)                 # (F, N)
            cols = []
            for k in range(1, self.K + 1):
                cols.append(np.sin(k * w)); cols.append(np.cos(k * w))
            X = np.concatenate([np.stack(cols, axis=-1),
                                np.broadcast_to(self.G, (len(fs),) + self.G.shape)], axis=-1)
            XW = X * self.w[None, :, None]
            A = np.einsum("fni,fnj->fij", XW, X) + self.Lam  # (F, p, p)
            r = np.einsum("fni,n->fi", XW, self.y)
            L = np.linalg.cholesky(A)
            z = np.linalg.solve(L, r[..., None])[..., 0]
            logdet = np.log(np.diagonal(L, axis1=1, axis2=2)).sum(axis=1)
            out[s0:s0 + chunk] = (-0.5 * self.yWy + 0.5 * (z * z).sum(1) - logdet
                                  + 0.5 * self.logdetLam_h)
        return out

    def log_post(self, f):
        if f < self.f_min or f > self.f_max:
            return -np.inf
        return self.log_like(f)

    def best_fit(self, f):
        """theta_hat and model curve at frequency f (posterior mean of theta)."""
        X = design(self.t, f, self.K, self.G)
        XW = X * self.w[:, None]
        theta = np.linalg.solve(X.T @ XW + self.Lam, XW.T @ self.y)
        return theta, X @ theta

    def calibrate_noise(self, f):
        """Empirical-Bayes noise scale: survey error bars are usually too small.
        Choose s so the reduced chi-square of the best fit at f is 1 (never below 1)."""
        _, m = self.best_fit(f)
        chi2 = np.sum(((self.y - m) / self.sigma) ** 2)
        dof = max(len(self.y) - (2 * self.K + self.G.shape[1]), 1)
        s = max(1.0, np.sqrt(chi2 / dof))
        self.set_noise_scale(s)
        return s
