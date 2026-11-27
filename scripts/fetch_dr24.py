"""Download current ZTF light curves (IRSA, latest public release) for a list of stars.

Usage: python scripts/fetch_dr24.py <list.csv with SourceID, ra, dec> [threads]
Saves one small parquet per star in data/raw/dr24/ (skips stars already fetched).
"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.ztf import fetch_irsa

OUTDIR = "data/raw/dr24"


def one(sid, ra, dec):
    path = f"{OUTDIR}/{sid}.parquet"
    if os.path.exists(path):
        return sid, "cached"
    try:
        df = fetch_irsa(ra, dec, band="r")
    except Exception as ex:
        return sid, f"error:{type(ex).__name__}"
    df = df[["oid", "mjd", "mag", "magerr", "field", "ccdid"]] if len(df) else pd.DataFrame(
        columns=["oid", "mjd", "mag", "magerr", "field", "ccdid"])
    df.to_parquet(path)
    return sid, len(df)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    lst = pd.read_csv(sys.argv[1])
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    t0, n = time.time(), 0
    with ThreadPoolExecutor(threads) as ex:
        futs = [ex.submit(one, int(r.SourceID), r.ra, r.dec) for r in lst.itertuples()]
        for f in as_completed(futs):
            n += 1
            if n % 100 == 0:
                print(f"{n}/{len(futs)}  {n / (time.time() - t0):.2f}/s", flush=True)
    print("done", n)


if __name__ == "__main__":
    main()
