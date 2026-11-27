"""Run the periodogram-guided Metropolis-Hastings sampler on every star in the sample.

Usage: python scripts/run_survey.py [max_stars]

Writes results/survey_dr2.csv incrementally (safe to stop and restart: stars
already done are skipped). Uses all CPU cores.
"""
import os, sys, time
import multiprocessing as mp
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve
from starsearch.sampler import analyse
from starsearch.compare import relation

LC_PATH = "data/raw/sample_lc_dr2.parquet"
OUT = "results/survey_dr2.csv"
K, F_MAX = 3, 10.0
_G = {}
COLS = ["SourceID", "Type", "Per_cat", "N", "T", "status", "f1", "p1", "sd1", "f2", "p2", "f3", "p3",
        "rhat", "p1_spread", "acc_rw", "acc_ind", "f_quad", "p_quad", "f_ls", "ls_power", "log_bf",
        "noise_scale", "n_cands", "rel", "rel_quad", "seconds"]


def _init():
    lc = pd.read_parquet(LC_PATH)
    ids = lc.SourceID.values
    starts = np.r_[0, np.where(np.diff(ids) != 0)[0] + 1]
    _G["ids"] = ids[starts]
    _G["bounds"] = dict(zip(ids[starts], zip(starts, np.r_[starts[1:], len(ids)])))
    _G["t"], _G["y"], _G["e"] = lc.mjd.values, lc.mag.values, lc.magerr.values


def work(row):
    sid, per, typ = row
    a, b = _G["bounds"][sid]
    t, y, e = _G["t"][a:b], _G["y"][a:b], np.maximum(_G["e"][a:b], 0.005)
    out = {"SourceID": sid, "Type": typ, "Per_cat": per, "N": b - a}
    if b - a < 20:
        out["status"] = "too_few"
        return out
    rng = np.random.default_rng(int(sid))
    t0 = time.time()
    try:
        lc = LightCurve(t, y, e, K=K, f_max=F_MAX)
        r = analyse(lc, rng)
    except Exception as ex:                      # keep going; record the failure
        out["status"] = f"error:{type(ex).__name__}"
        return out
    out.update(r)
    out["T"] = lc.T
    out["rel"] = relation(r["f1"], 1 / per, lc.T, tol_cycles=1.5)
    out["rel_quad"] = relation(r["f_quad"], 1 / per, lc.T, tol_cycles=1.5)
    out["seconds"] = time.time() - t0
    out["status"] = "ok"
    return out


def main():
    os.makedirs("results", exist_ok=True)
    sample = pd.read_parquet("data/raw/sample.parquet")
    done = set(pd.read_csv(OUT).SourceID) if os.path.exists(OUT) else set()
    lc_ids = set(pd.read_parquet(LC_PATH, columns=["SourceID"]).SourceID.unique())
    todo = sample[sample.SourceID.isin(lc_ids) & ~sample.SourceID.isin(done)].sample(frac=1, random_state=1)
    if len(sys.argv) > 1:
        todo = todo.head(int(sys.argv[1]))
    rows = list(zip(todo.SourceID.astype(int), todo.Per, todo.Type))
    print(f"{len(done)} done, {len(rows)} to go", flush=True)
    buf, t0 = [], time.time()
    with mp.Pool(os.cpu_count(), initializer=_init) as pool:
        for i, res in enumerate(pool.imap_unordered(work, rows, chunksize=20), 1):
            buf.append(res)
            if len(buf) >= 500 or i == len(rows):
                pd.DataFrame(buf).reindex(columns=COLS).to_csv(OUT, mode="a", header=not os.path.exists(OUT), index=False)
                buf = []
                rate = i / (time.time() - t0)
                print(f"{i}/{len(rows)}  {rate:.1f} stars/s  eta {(len(rows) - i) / rate / 60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
