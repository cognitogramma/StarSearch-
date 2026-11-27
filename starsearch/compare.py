"""How does a recovered frequency relate to a reference (catalogue) frequency?"""
import numpy as np

SIDEREAL = 1.0027379


def relation(f, f_ref, T, tol_cycles=0.5):
    """Classify f against f_ref.

    'match'    same frequency (within tol_cycles / T)
    'half'     f = f_ref / 2   (we found twice the period; common for eclipsing binaries)
    'double'   f = 2 f_ref     (we found half the period; ditto)
    'alias'    f = |f_ref +- k * sidereal day|, k = 1, 2  (daily aliasing)
    'alias2x'  an alias of 2 f_ref or f_ref / 2
    'other'
    """
    if not np.isfinite(f):
        return "none"
    tol = tol_cycles / T
    if abs(f - f_ref) < tol:
        return "match"
    if abs(f - f_ref / 2) < tol:
        return "half"
    if abs(f - 2 * f_ref) < tol:
        return "double"
    for base, name in ((f_ref, "alias"), (2 * f_ref, "alias2x"), (f_ref / 2, "alias2x")):
        for k in (1, 2):
            if abs(f - abs(base - k * SIDEREAL)) < tol or abs(f - (base + k * SIDEREAL)) < tol:
                return name
    return "other"


def same_or_harmonic(f, f_ref, T):
    """True when f gives the right star *period* up to the usual factor of 2."""
    return relation(f, f_ref, T) in ("match", "half", "double")
