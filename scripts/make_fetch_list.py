"""Choose prediction targets from the DR2 survey results.

disagree: pulsators (RR, RRc, CEP, CEPII) whose confident top period is not the
          catalogue period -> candidate catalogue errors / misclassified stars
ambiguous: any type with no dominant peak (p1 < 0.8)
Excludes stars already listed in earlier fetch lists."""
import glob, sys
import pandas as pd
d = pd.read_csv("results/survey_dr2.csv"); d = d[d.status == "ok"]
cat = pd.read_parquet("data/raw/sample.parquet")[["SourceID", "ID", "ra", "dec", "Per", "Per_g", "Per_r"]]
seen = set(pd.concat([pd.read_csv(f) for f in glob.glob("predictions/fetch_list_*.csv")]).SourceID)
pul = d.Type.isin(["RR", "RRc", "CEP", "CEPII"])
dis = d[pul & (d.rel != "match") & (d.p1 >= 0.95)].assign(reason="dr2_disagree")
amb = d[(d.p1 < 0.8) & d.Type.isin(["RR", "RRc", "CEP", "CEPII", "EW", "EA"])].assign(reason="dr2_ambiguous")
lst = pd.concat([dis, amb]).drop_duplicates("SourceID")
lst = lst[~lst.SourceID.isin(seen)][["SourceID", "Type", "reason"]].merge(cat, on="SourceID")
out = sys.argv[1]
lst.to_csv(out, index=False)
print(len(lst), lst.reason.value_counts().to_dict())
