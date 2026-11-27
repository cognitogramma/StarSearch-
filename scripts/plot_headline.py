"""Folded light curves for headline 'true period is 2x catalogue' predictions:
left = folded at the catalogue period, right = folded at twice it."""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.ztf import clean
from starsearch.model import LightCurve

h = pd.read_csv("predictions/headline_v1.csv")
ids = pd.read_csv("predictions/predictions_v1.csv")[["ID"]].merge(
    pd.concat([pd.read_csv(f) for f in ["predictions/fetch_list_1.csv", "predictions/fetch_list_2.csv"]])[["ID", "SourceID"]].drop_duplicates(), on="ID")
sel = h[h.prediction.str.startswith("true period is 2x")].merge(ids, on="ID").head(4)
fig, axes = plt.subplots(len(sel), 2, figsize=(10, 2.3 * len(sel)), squeeze=False)
for row, (ax1, ax2) in zip(sel.itertuples(), axes):
    d = pd.read_parquet(f"data/raw/dr24/{row.SourceID}.parquet")
    g = (d.field.astype(str) + "_" + d.ccdid.astype(str)).values
    t, y, e, g = clean(d.mjd.values, d.mag.values, d.magerr.values, g)
    lc = LightCurve(t, y, e, K=3, groups=g)
    theta, _ = lc.best_fit(1 / row.P1)
    yc = y - lc.G @ theta[2 * lc.K:] + np.median(lc.G @ theta[2 * lc.K:])   # remove field offsets
    for ax, P, lab, col in ((ax1, row.Per_cat, "catalogue", "#5c5b57"), (ax2, row.P1, "ours (2x)", "#2a78d6")):
        ph = (t / P) % 1
        ax.scatter(np.r_[ph, ph + 1], np.r_[yc, yc], s=3, color=col, alpha=0.5)
        ax.invert_yaxis(); ax.set_yticks([]); ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_title(f"{row.ID} ({row.Type}) folded at {lab} P = {P:.5f} d", fontsize=9, loc="left")
axes[-1][0].set_xlabel("phase"); axes[-1][1].set_xlabel("phase")
fig.tight_layout(); fig.savefig("figs/headline_doubled.png", dpi=200); print(sel[["ID", "Type", "Per_cat", "P1"]])
