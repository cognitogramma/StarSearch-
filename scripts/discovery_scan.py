"""Discovery scan: look for periodic variables that are NOT in the ZTF periodic-variable
catalogue (Chen et al. 2020).

For random 30-arcsecond patches of the Galactic plane (where most variables are),
download every ZTF r-band light curve, merge records of the same star, keep stars with >= 100 good points, and
score each with a fast periodogram plus our Bayes factor (periodic vs constant).
Strong detections are cross-matched against the catalogue; unmatched ones are
saved as candidates (with their light curves) for a full MH analysis.

Usage: python scripts/discovery_scan.py [n_cones] [threads]
Resumable: cones already scanned are skipped.
"""
import io, os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.timeseries import LombScargle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve
from starsearch.ztf import clean

OUT = "results/discovery"
RAD = 30 / 3600
URL = "https://irsa.ipac.caltech.edu/cgi-bin/ZTF/nph_light_curves?POS=CIRCLE%20{ra:.5f}%20{dec:.5f}%20{rad:.6f}&BANDNAME=r&FORMAT=csv&BAD_CATFLAGS_MASK=65535"


def cones(n, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n:
        l = rng.uniform(0, 360); b = rng.uniform(-10, 10)
        c = SkyCoord(l=l * u.deg, b=b * u.deg, frame="galactic").icrs
        if c.dec.deg > -25:                                  # ZTF's sky
            out.append((len(out), c.ra.deg, c.dec.deg))
    return out


def score(t, y, e, groups=None):
    lc = LightCurve(t, y, e, K=3, f_max=10.0, groups=groups)
    freq = np.arange(lc.f_min, lc.f_max, 1 / (5 * lc.T))
    ls = LombScargle(lc.t, lc.y, lc.sigma)
    p = ls.power(freq, method="fast")
    i = int(np.argmax(p)); f = freq[i]
    # avoid the classic false signals: 1 day and its harmonics, ~29.5 d (Moon), ~1 yr
    bad = any(abs(f - k * 1.0027379) < 0.01 for k in (1, 2, 3)) or abs(f - 1 / 29.53) < 0.004 or f < 1 / 200
    lc.calibrate_noise(f)
    g = np.linspace(f - 1.5 / lc.T, f + 1.5 / lc.T, 31)
    ll = lc.log_like_many(g)
    log_bf = ll.max() + np.log(np.trapezoid(np.exp(ll - ll.max()), g)) - np.log(lc.f_max - lc.f_min) - lc.logZ_const
    _, m = lc.best_fit(g[np.argmax(ll)])
    amp = np.percentile(m, 95) - np.percentile(m, 5)
    return dict(f_ls=float(f), ls_power=float(p[i]), fap=float(ls.false_alarm_probability(p[i], minimum_frequency=lc.f_min, maximum_frequency=lc.f_max)),
                log_bf=float(log_bf), amp=float(amp), noise_scale=float(lc.s), artefact_freq=bool(bad))


def scan(cone, cat_xy):
    k, ra, dec = cone
    path = f"{OUT}/cones/{k:05d}.json"
    if os.path.exists(path):
        return k, "cached"
    try:
        txt = urllib.request.urlopen(URL.format(ra=ra, dec=dec, rad=RAD), timeout=400).read().decode()
    except Exception as ex:
        return k, f"error:{type(ex).__name__}"
    rows = []
    if txt.strip():
        d = pd.read_csv(io.StringIO(txt))
        d = d[d.catflags == 0]
        # one star often appears as several ZTF records (overlapping fields/CCDs):
        # merge records within 1.5" and give each record its own zero-point
        pos = d.groupby("oid")[["ra", "dec"]].median()
        star_of, centres = {}, []
        for oid, r in pos.iterrows():
            for j, (cra, cdec) in enumerate(centres):
                if np.hypot((r.ra - cra) * np.cos(np.radians(cdec)), r.dec - cdec) * 3600 < 1.5:
                    star_of[oid] = j; break
            else:
                star_of[oid] = len(centres); centres.append((r.ra, r.dec))
        d = d.assign(star=d.oid.map(star_of))
        for sidx, g in d.groupby("star"):
            if len(g) < 100:
                continue
            t, y, e, grp = clean(g.mjd.values, g.mag.values, g.magerr.values, g.oid.values)
            if len(t) < 100:
                continue
            s = score(t, y, e, grp)
            sra, sdec = centres[sidx]
            oid = int(g.oid.value_counts().index[0])
            dra = (cat_xy[0] - sra) * np.cos(np.radians(sdec)); ddec = cat_xy[1] - sdec
            near = np.where((np.abs(ddec) < 3 / 3600) & (np.abs(dra) < 3 / 3600))[0]
            sep = float(np.min(np.hypot(dra[near], ddec[near])) * 3600) if len(near) else None
            row = dict(cone=k, oid=oid, n_records=int(g.oid.nunique()), ra=float(sra), dec=float(sdec),
                       N=int(len(t)), mag=float(np.median(y)), in_catalog=sep is not None and sep < 2.0,
                       cat_sep=sep, **s)
            rows.append(row)
            strong = s["fap"] < 1e-10 and s["log_bf"] > 20 and not s["artefact_freq"] and s["amp"] > 0.03
            if strong and not row["in_catalog"]:
                g[["oid", "mjd", "mag", "magerr", "field", "ccdid"]].to_parquet(f"{OUT}/candidates/{oid}.parquet")
    json.dump(rows, open(path, "w"))
    return k, len(rows)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    os.makedirs(f"{OUT}/cones", exist_ok=True); os.makedirs(f"{OUT}/candidates", exist_ok=True)
    cat = pd.read_parquet("data/raw/ztf_cpvs_catalog.parquet", columns=["ra", "dec"])
    cat_xy = (cat.ra.values, cat.dec.values)
    cs = cones(n)
    t0 = time.time(); done = 0
    with ThreadPoolExecutor(threads) as ex:
        futs = [ex.submit(scan, c, cat_xy) for c in cs]
        for f in as_completed(futs):
            done += 1
            k, res = f.result()
            print(f"{done}/{n} cone {k}: {res}  ({(time.time() - t0) / done:.0f}s/cone)", flush=True)


if __name__ == "__main__":
    main()
