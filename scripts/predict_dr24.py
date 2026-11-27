"""Period posteriors from the latest ZTF light curves (fetched by fetch_dr24.py).

Usage: python scripts/predict_dr24.py <list.csv> <out.csv>

Each ZTF field/CCD gets its own zero-point (integrated out exactly). More chains
and steps than the survey, because these results are the published predictions.
"""
import os, sys, time
import multiprocessing as mp
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve
from starsearch.sampler import analyse
from starsearch.ztf import clean
from starsearch.compare import relation

K, F_MAX = 3, 10.0
COLS = ["SourceID", "ID", "ra", "dec", "Type", "Per_cat", "reason", "N", "T", "mjd_min", "mjd_max",
        "status", "P1", "p1", "P1_sd", "P2", "p2", "P3", "p3", "rhat", "p1_spread", "acc_rw", "acc_ind",
        "log_bf", "noise_scale", "rel_cat", "seconds",
        "N_new", "P1_new", "p1_new", "P2_new", "p2_new", "rhat_new"]
DR2_END = 58730.0   # last DR2 epoch is MJD 58725; later points are new, independent data


def work(row):
    out = {k: getattr(row, k) for k in ("SourceID", "ID", "ra", "dec", "Type", "reason")}
    out["Per_cat"] = row.Per
    path = f"data/raw/dr24/{int(row.SourceID)}.parquet"
    if not os.path.exists(path):
        out["status"] = "no_data"; return out
    d = pd.read_parquet(path)
    if len(d) < 30:
        out["status"] = "too_few"; return out
    grp = (d.field.astype(int) * 100 + d.ccdid.astype(int)).values
    t, y, e, g = clean(d.mjd.values, d.mag.values, d.magerr.values, grp)
    # drop tiny groups (a handful of points cannot pin down their own offset)
    keep = pd.Series(g).map(pd.Series(g).value_counts()).values >= 10
    t, y, e, g = t[keep], y[keep], e[keep], g[keep]
    if len(t) < 30:
        out["status"] = "too_few"; return out
    t0 = time.time()
    rng = np.random.default_rng(int(row.SourceID) + 7)
    try:
        lc = LightCurve(t, y, e, K=K, f_max=F_MAX, groups=g)
        r = analyse(lc, rng, n_chains=4, n_steps=3000, burn=600)
    except Exception as ex:
        out["status"] = f"error:{type(ex).__name__}"; return out
    inv = lambda f: 1 / f if np.isfinite(f) and f > 0 else np.nan
    out.update({"N": len(t), "T": lc.T, "mjd_min": t.min(), "mjd_max": t.max(), "status": "ok",
                "P1": inv(r["f1"]), "p1": r["p1"], "P1_sd": r["sd1"] / r["f1"] ** 2,
                "P2": inv(r["f2"]), "p2": r["p2"], "P3": inv(r["f3"]), "p3": r["p3"],
                "rhat": r["rhat"], "p1_spread": r["p1_spread"], "acc_rw": r["acc_rw"],
                "acc_ind": r["acc_ind"], "log_bf": r["log_bf"], "noise_scale": r["noise_scale"],
                "rel_cat": relation(r["f1"], 1 / row.Per, lc.T, tol_cycles=1.5),
                "seconds": time.time() - t0})
    # independent check: the same analysis on post-DR2 data only
    new = t > DR2_END
    if new.sum() >= 30 and len(np.unique(g[new])) >= 1:
        try:
            lc2 = LightCurve(t[new], y[new], e[new], K=K, f_max=F_MAX, groups=g[new])
            r2 = analyse(lc2, rng, n_chains=3, n_steps=2000, burn=400)
            out.update({"N_new": int(new.sum()), "P1_new": inv(r2["f1"]), "p1_new": r2["p1"],
                        "P2_new": inv(r2["f2"]), "p2_new": r2["p2"], "rhat_new": r2["rhat"]})
        except Exception:
            pass
    return out


def main():
    lst = pd.read_csv(sys.argv[1]); out = sys.argv[2]
    done = set(pd.read_csv(out).SourceID) if os.path.exists(out) else set()
    rows = [r for r in lst.itertuples() if r.SourceID not in done]
    print(len(rows), "to do", flush=True)
    buf = []
    with mp.Pool(os.cpu_count()) as pool:
        for i, res in enumerate(pool.imap_unordered(work, rows, chunksize=4), 1):
            buf.append(res)
            if len(buf) >= 100 or i == len(rows):
                pd.DataFrame(buf).reindex(columns=COLS).to_csv(out, mode="a", header=not os.path.exists(out), index=False)
                buf = []
                print(i, flush=True)


if __name__ == "__main__":
    main()
