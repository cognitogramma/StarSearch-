"""Scan whole ZTF DR24 bulk light-curve files (one field/CCD/quadrant, r band) for
periodic variables that are NOT in the ZTF periodic-variable catalogue.

Usage: python scripts/bulk_scan.py <file-list.txt> [target_stars] [workers]
Each line of the list is a path under https://irsa.ipac.caltech.edu/data/ZTF/lc/lc_dr24/.
Per file: download -> score every star with >= 100 good points -> write
results/bulk/<file>.parquet (all scores) and save light curves of strong, uncatalogued
signals to results/bulk/candidates/<oid>.npz -> delete the download. Resumable: files
with a finished score table are skipped. A next file is pre-downloaded while one is scored.
"""
import os, sys, time, threading, urllib.request, queue
import multiprocessing as mp
import numpy as np, pandas as pd
import pyarrow.parquet as pq
import nifty_ls                      # fast periodogram for screening (about 16x astropy's)
from astropy.timeseries import LombScargle
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve

BASE = "https://irsa.ipac.caltech.edu/data/ZTF/lc/lc_dr24/"
RAW = "data/raw/bulk"
OUT = "results/bulk"
MIN_N = 100
SYN = 29.530589


def unit(ra, dec):
    ra, dec = np.radians(ra), np.radians(dec)
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def calendar_bad(f):
    if any(abs(f - k) < 0.02 * k for k in (1, 2, 3)) or abs(f - 1.0027379) < 0.01:
        return True
    moon = [1 / SYN, 1 / 27.321662] + [k + s / SYN for k in (1, 2, 1.0027379) for s in (-1, 1)]
    return any(abs(f - m) < 0.003 for m in moon) or f < 3 / 365.25


def score(t, y, e):
    lc = LightCurve(t, y, e, K=3, f_max=10.0)
    n = int((lc.f_max - lc.f_min) * 5 * lc.T)
    r = nifty_ls.lombscargle(lc.t, lc.y, dy=lc.sigma, fmin=lc.f_min, fmax=lc.f_max, Nf=n)
    p = r.power; freq = r.freq()
    i = int(np.argmax(p)); f = float(freq[i])
    fap = float(LombScargle(lc.t, lc.y, lc.sigma).false_alarm_probability(
        p[i], minimum_frequency=lc.f_min, maximum_frequency=lc.f_max))
    lc.calibrate_noise(f)
    g = np.linspace(f - 1.5 / lc.T, f + 1.5 / lc.T, 31)
    ll = lc.log_like_many(g)
    log_bf = ll.max() + np.log(np.trapezoid(np.exp(ll - ll.max()), g)) - np.log(lc.f_max - lc.f_min) - lc.logZ_const
    _, m = lc.best_fit(g[np.argmax(ll)])
    amp = float(np.percentile(m, 95) - np.percentile(m, 5))
    return float(g[np.argmax(ll)]), float(p[i]), fap, float(log_bf), amp, float(lc.s)


def work(args):
    oid, ra, dec, t, y, e = args
    try:
        f, pw, fap, lbf, amp, s = score(t, y, e)
    except Exception:
        return None
    return dict(oid=oid, ra=ra, dec=dec, N=len(t), mag=float(np.median(y)), T=float(t.max() - t.min()),
                f=f, power=pw, fap=fap, log_bf=lbf, amp=amp, noise_scale=s, calendar=calendar_bad(f))


def stars_in(path, batch_size=4000):
    """Yield lists of (oid, ra, dec, t, y, e) per parquet batch: whole files do not fit in memory."""
    pf = pq.ParquetFile(path)
    cols = ["objectid", "objra", "objdec", "nepochs", "hmjd", "mag", "magerr", "catflags"]
    for batch in pf.iter_batches(batch_size=batch_size, columns=cols):
        keep = batch.column("nepochs").to_numpy() >= MIN_N
        d = batch.filter(keep).to_pydict()
        out = []
        for k in range(len(d["objectid"])):
            ok = np.asarray(d["catflags"][k]) == 0
            if ok.sum() < MIN_N:
                continue
            t = np.asarray(d["hmjd"][k])[ok]; y = np.asarray(d["mag"][k], float)[ok]; e = np.asarray(d["magerr"][k], float)[ok]
            good = np.isfinite(t) & np.isfinite(y) & np.isfinite(e) & (e > 0)
            t, y, e = t[good], y[good], np.maximum(e[good], 0.005)
            med = np.median(y); mad = 1.4826 * np.median(np.abs(y - med)) + 1e-9
            sel = np.abs(y - med) < max(5 * mad, 3 * (np.percentile(y, 95) - np.percentile(y, 5)))
            if sel.sum() >= MIN_N:
                out.append((int(d["objectid"][k]), float(d["objra"][k]), float(d["objdec"][k]), t[sel], y[sel], e[sel]))
        yield out


def downloader(files, q):
    for rel in files:
        name = os.path.basename(rel)
        if os.path.exists(f"{OUT}/{name}"):
            continue
        dst = f"{RAW}/{name}"
        for attempt in range(4):
            try:
                if not os.path.exists(dst):
                    urllib.request.urlretrieve(BASE + rel, dst + ".part"); os.replace(dst + ".part", dst)
                break
            except Exception:
                time.sleep(10 * (attempt + 1))
        q.put(dst if os.path.exists(dst) else None)
    q.put("DONE")


def scored_so_far():
    return sum(pq.ParquetFile(f"{OUT}/{n}").metadata.num_rows for n in os.listdir(OUT) if n.endswith(".parquet"))


def main():
    files = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 12
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else os.cpu_count()
    os.makedirs(RAW, exist_ok=True); os.makedirs(f"{OUT}/candidates", exist_ok=True)
    done = scored_so_far()
    if done >= target:
        print(f"target reached: {done} stars scored"); return
    cat = pd.read_parquet("data/raw/ztf_cpvs_catalog.parquet", columns=["ID", "ra", "dec"])
    tree = cKDTree(unit(cat.ra.values, cat.dec.values))
    q = queue.Queue(maxsize=1)
    threading.Thread(target=downloader, args=(files, q), daemon=True).start()
    with mp.Pool(workers) as pool:
        while done < target:
            path = q.get()
            if path == "DONE":
                break
            if path is None:
                print("download failed", flush=True); continue
            t0 = time.time(); name = os.path.basename(path); parts = []
            for stars in stars_in(path):
                rows = [r for r in pool.imap_unordered(work, stars, chunksize=32) if r]
                if not rows:
                    continue
                df = pd.DataFrame(rows)
                dist, _ = tree.query(unit(df.ra.values, df.dec.values))
                df["cat_sep"] = np.degrees(2 * np.arcsin(np.clip(dist / 2, 0, 1))) * 3600
                df["in_catalog"] = df.cat_sep < 2.0
                df["strong"] = (df.fap < 1e-10) & (df.log_bf > 20) & (df.amp > 0.03) & ~df.calendar
                lcs = {s_[0]: s_ for s_ in stars}
                for r in df[df.strong & ~df.in_catalog].itertuples():
                    _, ra, dec, t, y, e = lcs[r.oid]
                    np.savez_compressed(f"{OUT}/candidates/{r.oid}.npz", t=t, y=y, e=e, ra=ra, dec=dec)
                parts.append(df)
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            df.to_parquet(f"{OUT}/{name}")
            os.remove(path)
            done += len(df)
            print(f"{name}: {len(df)} stars scored, {int(df.strong.sum()) if len(df) else 0} strong, "
                  f"{int((df.strong & ~df.in_catalog).sum()) if len(df) else 0} strong & uncatalogued, "
                  f"{time.time() - t0:.0f}s; total {done}", flush=True)
    print(f"finished: {done} stars scored", flush=True)


if __name__ == "__main__":
    main()
