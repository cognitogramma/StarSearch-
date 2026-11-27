"""Pull the sample's light curves out of the 1.9 GB DR2 file (ztf2r inside ztf2r.zip).
Columns in the file: SourceID, ra, dec, mjd, mag, magerr, flag. Keeps flag == 0."""
import subprocess, numpy as np, pandas as pd
ids = set(pd.read_parquet("data/raw/sample.parquet").SourceID.astype(int))
cols = ["SourceID", "ra", "dec", "mjd", "mag", "magerr", "flag"]
out = []
# The published zip has a bad CRC on this member even though the download matches
# Zenodo's md5, so stream it with `unzip -p` (which still outputs the data).
proc = subprocess.Popen(["unzip", "-p", "data/raw/ztf2r.zip", "ztf2r"], stdout=subprocess.PIPE)
with proc.stdout as fh:
    for i, ch in enumerate(pd.read_csv(fh, names=cols, header=None, chunksize=2_000_000,
                                       dtype={"SourceID": np.int64})):
        ch = ch[ch.SourceID.isin(ids) & (ch.flag == 0)]
        out.append(ch[["SourceID", "mjd", "mag", "magerr"]])
        if i % 5 == 0:
            print(i, sum(len(o) for o in out), flush=True)
lc = pd.concat(out).sort_values(["SourceID", "mjd"])
lc.to_parquet("data/raw/sample_lc_dr2.parquet")
print("rows", len(lc), "stars", lc.SourceID.nunique())
