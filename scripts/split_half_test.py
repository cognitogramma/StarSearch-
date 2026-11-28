"""Repeatability test for graded bulk candidates: is the top period detected independently
in the first half and in the second half of the light curve?

At one fixed frequency, the false-alarm probability of standard Lomb-Scargle power p with N
points is (1 - p)^((N - 3) / 2). A star passes when both halves give < 1e-6 at its period
(or at twice it, which an eclipsing binary may prefer). Artefacts driven by a few nights
(vertical stripes in the folded curve) fail in at least one half.
Writes results/bulk_shortlist_final.csv (grade A2 = grade A that passes)."""
import numpy as np, pandas as pd
from astropy.timeseries import LombScargle

s = pd.read_csv("results/bulk_shortlist.csv")
rows = []
for r in s[s.grade.isin(["A", "B"])].itertuples():
    z = np.load(f"results/bulk/candidates/{r.oid}.npz")
    t, y, e = z["t"], z["y"], z["e"]
    mid = np.median(t)
    best = []
    for half in (t < mid, t >= mid):
        th, yh, eh = t[half], y[half], e[half]
        n = len(th)
        ps = [LombScargle(th, yh, eh, nterms=1).power(f) for f in (1 / r.P1, 0.5 / r.P1)]
        best.append(max(0.0, (1 - max(ps)) ** ((n - 3) / 2)) if n > 10 else 1.0)
    rows.append(dict(oid=r.oid, fap_half1=best[0], fap_half2=best[1], repeats=max(best) < 1e-6))
x = s.merge(pd.DataFrame(rows), on="oid", how="left")
x["final_grade"] = x.grade
x.loc[(x.grade == "A") & (x.repeats == True), "final_grade"] = "A2"
x.loc[(x.grade == "B") & (x.repeats == True), "final_grade"] = "B2"
x.to_csv("results/bulk_shortlist_final.csv", index=False)
print(x[x.grade.isin(["A", "B"])].groupby("grade").repeats.agg(["sum", "size"]))
