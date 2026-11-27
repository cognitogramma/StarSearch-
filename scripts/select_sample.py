"""Pick the survey sample from the ZTF periodic-variable catalogue.

Types whose periods lie in 0.1-50 d (frequency 0.02-10 cycles/day), where our
harmonic model is reasonable and DR2's ~1.5-year baseline covers many cycles.
Fixed random seed so the sample is reproducible."""
import numpy as np, pandas as pd
c = pd.read_parquet("data/raw/ztf_cpvs_catalog.parquet")
quota = {"RR": 32518, "RRc": 13875, "CEP": 1262, "CEPII": 358,
         "EW": 22795, "EA": 15000, "BYDra": 9000, "RSCVN": 8000}
c = c[(c.Per > 0.1) & (c.Per < 50) & (c.Num_r >= 20)]
parts = []
for typ, n in quota.items():
    sub = c[c.Type == typ]
    parts.append(sub.sample(min(n, len(sub)), random_state=2026))
s = pd.concat(parts)
s.to_parquet("data/raw/sample.parquet")
print(len(s)); print(s.Type.value_counts())
