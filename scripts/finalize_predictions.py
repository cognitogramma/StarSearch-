"""Assemble the published prediction table and the out-of-sample check.

Inputs : results/pred_raw_*.csv (from predict_dr24.py), results/survey_dr2.csv
Outputs: predictions/predictions_v1.csv, predictions/SHA256SUMS,
         results/prediction_check.json, figs/pred_*.png
"""
import glob, hashlib, json, subprocess, datetime
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.compare import relation

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1b1b1b", "#5c5b57", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
                     "savefig.dpi": 200, "savefig.bbox": "tight"})

raw = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("results/pred_raw_*.csv"))]).drop_duplicates("SourceID")
ok = raw[raw.status == "ok"].copy()

# ---- 1. the published table ------------------------------------------------
cols = ["ID", "ra", "dec", "Type", "Per_cat", "reason", "P1", "p1", "P1_sd", "P2", "p2", "P3", "p3",
        "rel_cat", "rhat", "p1_spread", "N", "T", "mjd_min", "mjd_max"]
pub = ok[cols].sort_values(["reason", "ID"])
pub.to_csv("predictions/predictions_v1.csv", index=False, float_format="%.7g")
h = hashlib.sha256(open("predictions/predictions_v1.csv", "rb").read()).hexdigest()
open("predictions/SHA256SUMS", "w").write(f"{h}  predictions_v1.csv\n")

# ---- 2. out-of-sample check: DR2 posterior vs post-DR2 data only ------------
sv = pd.read_csv("results/survey_dr2.csv")[["SourceID", "f1", "p1", "f2", "p2", "T"]].rename(
    columns={"f1": "f1_dr2", "p1": "p1_dr2", "f2": "f2_dr2", "p2": "p2_dr2", "T": "T_dr2"})
chk = ok.merge(sv, on="SourceID").dropna(subset=["P1_new", "f1_dr2"])
chk = chk[chk.p1_new >= 0.9]                      # use only confident new-data periods as "truth"
f_new = 1 / chk.P1_new
chk["dr2_right"] = [relation(a, b, T, tol_cycles=1.5) == "match" for a, b, T in zip(chk.f1_dr2, f_new, chk.T_dr2)]
chk["cat_right"] = [relation(1 / a, b, T, tol_cycles=1.5) == "match" for a, b, T in zip(chk.Per_cat, f_new, chk.T_dr2)]
unbiased = chk[chk.reason.isin(["control", "g_r_disagree"])]       # not selected using our posterior
bins = np.array([0, 0.5, 0.7, 0.9, 0.99, 1.0001])
u = unbiased.assign(b=pd.cut(unbiased.p1_dr2, bins, right=False))
cal = u.groupby("b", observed=True).agg(n=("dr2_right", "size"), stated=("p1_dr2", "mean"), actual=("dr2_right", "mean"))

dis = chk[chk.reason == "dr2_disagree"]
S = {
    "made_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "git_commit_of_code": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
    "n_predictions": int(len(pub)), "sha256_predictions_v1": h,
    "by_reason": pub.reason.value_counts().to_dict(),
    "new_data_check": {
        "n_stars_with_confident_new_period": int(len(chk)),
        "calibration_unbiased_subset": [{"stated": round(r.stated, 3), "actual": round(r.actual, 3), "n": int(r.n)}
                                        for r in cal.itertuples()],
        "where_DR2_posterior_disagreed_with_catalogue": {
            "n": int(len(dis)),
            "new_data_sides_with_our_DR2_period": float(dis.dr2_right.mean()) if len(dis) else None,
            "new_data_sides_with_catalogue": float(dis.cat_right.mean()) if len(dis) else None,
        },
    },
}
json.dump(S, open("results/prediction_check.json", "w"), indent=2)
print(json.dumps(S, indent=2))

if len(cal):
    fig, ax = plt.subplots(figsize=(6, 5.4))
    ax.plot([0, 1], [0, 1], color=MUTED, ls="--", lw=1)
    ax.scatter(cal.stated, cal.actual, s=np.clip(cal.n / cal.n.max() * 400, 25, 400), color=ORANGE, zorder=3)
    for r in cal.itertuples():
        ax.annotate(f"n={r.n}", (r.stated, r.actual), xytext=(6, -14), textcoords="offset points", fontsize=10, color=MUTED)
    ax.set_xlim(0.3, 1.02); ax.set_ylim(0.3, 1.02)
    ax.set_xlabel("DR2 posterior probability of top period"); ax.set_ylabel("fraction confirmed by later ZTF data")
    ax.set_title("Out-of-sample check (2019–2025 data)")
    fig.savefig("figs/pred_calibration_newdata.png"); plt.close(fig)

# ---- 3. headline predictions: confident disagreements with the catalogue ----
# Compare at the catalogue's own precision (DR2 baseline ~450 d): smaller differences
# are refinements of the catalogue period, not disagreements.
T_CAT = 450.0
p = pub.copy()
p["rel_cat_dr2prec"] = [relation(1 / a, 1 / b, T_CAT, tol_cycles=1.5) for a, b in zip(p.P1, p.Per_cat)]
p.loc[(p.rel_cat != "match") & (p.rel_cat_dr2prec == "match"), "rel_cat_dr2prec"] = "refined"
head = p[p.Type.isin(["RR", "RRc", "CEP", "CEPII"]) & (p.p1 >= 0.95) &
         p.rel_cat_dr2prec.isin(["half", "double", "alias", "alias2x", "other"])].copy()
claim = {"half": "true period is 2x catalogue (binary misfiled as pulsator?)",
         "double": "true period is 1/2 catalogue",
         "alias": "catalogue period is a daily alias", "alias2x": "catalogue period is an alias of 2P or P/2",
         "other": "different period"}
head["prediction"] = head.rel_cat_dr2prec.map(claim)
head = head.sort_values(["rel_cat_dr2prec", "p1"], ascending=[True, False])
head[["ID", "ra", "dec", "Type", "Per_cat", "P1", "p1", "P1_sd", "P2", "p2", "prediction", "N", "T"]].to_csv(
    "predictions/headline_v1.csv", index=False, float_format="%.7g")
h2 = hashlib.sha256(open("predictions/headline_v1.csv", "rb").read()).hexdigest()
open("predictions/SHA256SUMS", "a").write(f"{h2}  headline_v1.csv\n")
S["headline"] = {"n": int(len(head)), "by_claim": head.rel_cat_dr2prec.value_counts().to_dict(),
                 "n_refined_not_disagreeing": int((p.rel_cat_dr2prec == "refined").sum()),
                 "sha256_headline_v1": h2}
json.dump(S, open("results/prediction_check.json", "w"), indent=2)
print("headline:", json.dumps(S["headline"]))
