"""Reading ZTF data: the Chen et al. (2020) periodic-variable catalogue, its
bundled DR2 light curves, and fresh light curves from the IRSA API."""
import io
import time
import urllib.request

import numpy as np
import pandas as pd

IRSA_LC = "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves"


def load_catalog(path="data/raw/ztf_cpvs_catalog.parquet"):
    return pd.read_parquet(path)


def clean(t, y, e, groups=None, clip=5.0, min_err=0.005):
    """Drop non-finite points and >clip-sigma outliers (robust, about the median)."""
    t, y, e = map(np.asarray, (t, y, e))
    ok = np.isfinite(t) & np.isfinite(y) & np.isfinite(e) & (e > 0)
    t, y, e = t[ok], y[ok], np.maximum(e[ok], min_err)
    g = None if groups is None else np.asarray(groups)[ok]
    med = np.median(y)
    mad = 1.4826 * np.median(np.abs(y - med)) + 1e-9
    keep = np.abs(y - med) < clip * max(mad, np.median(e))
    # a pulsating star can legitimately swing far from its median: be generous
    keep |= np.abs(y - med) < 3 * (np.percentile(y, 95) - np.percentile(y, 5))
    return t[keep], y[keep], e[keep], (None if g is None else g[keep])


def fetch_irsa(ra, dec, band="r", radius_arcsec=1.5, retries=3, timeout=60):
    """Latest public ZTF light curve (all fields/CCDs) around a position.
    Keeps only points with catflags == 0. Returns a DataFrame (may be empty)."""
    url = (f"{IRSA_LC}?POS=CIRCLE%20{ra:.6f}%20{dec:.6f}%20{radius_arcsec / 3600:.6f}"
           f"&BANDNAME={band}&FORMAT=csv&BAD_CATFLAGS_MASK=65535")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                txt = r.read().decode()
            df = pd.read_csv(io.StringIO(txt))
            return df[df["catflags"] == 0] if len(df) else df
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
