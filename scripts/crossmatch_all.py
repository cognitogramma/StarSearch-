"""Cross-match every discovery candidate (results/discovery_candidates.csv) against
variable-star catalogues on VizieR (Harvard mirror). Writes results/discovery_crossmatch.csv.
VSX here is VizieR's copy (B/vsx), which can lag the live VSX site."""
import io, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

MIRROR = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?"
CATS = {"vsx": "B/vsx/vsx", "gaia_dr3_var": "I/358/vclassre", "asassn": "II/366/catv2021",
        "atlas": "J/AJ/156/241/table4", "ztf_cpvs": "J/ApJS/249/18/table2"}
NAME_COL = {"vsx": ["Name", "Type", "Period"], "gaia_dr3_var": ["Source", "Class"], "asassn": ["ASASSN-V", "Type", "Per"],
            "atlas": ["ATOID", "Class", "fp-LSper"], "ztf_cpvs": ["ID", "Type", "Per"]}


def query(src, ra, dec, rad=10):
    q = urllib.parse.urlencode({"-source": src, "-c": f"{ra} {dec}", "-c.rs": str(rad), "-out.max": "3",
                                "-out.add": "_r", "-sort": "_r", "-out.all": ""})
    for attempt in range(3):
        try:
            txt = urllib.request.urlopen(MIRROR + q, timeout=90).read().decode()
            lines = [l for l in txt.splitlines() if l and not l.startswith("#")]
            if len(lines) <= 3:
                return None
            return dict(zip(lines[0].split("\t"), lines[3].split("\t")))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return "error"


def one(row):
    out = {"oid": row.oid}
    for k, src in CATS.items():
        m = query(src, row.ra, row.dec)
        if m == "error":
            out[k] = "error"
        elif m is None:
            out[k] = ""
        else:
            bits = [str(m.get(c, "")).strip() for c in NAME_COL[k] if m.get(c, "").strip()]
            out[k] = f"{float(m.get('_r', 'nan')):.1f}\" " + " | ".join(bits)
    return out


c = pd.read_csv("results/discovery_candidates.csv")
with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, c.itertuples()))
x = c.merge(pd.DataFrame(res), on="oid")
x["any_variable_catalogue"] = (x[list(CATS)].fillna("").astype(str).apply(lambda s: s.str.len() > 0 & ~s.eq("error"))).any(axis=1)
x["any_error"] = (x[list(CATS)] == "error").any(axis=1)
x.to_csv("results/discovery_crossmatch.csv", index=False)
print(len(x), "candidates; in a variable catalogue:", int(x.any_variable_catalogue.sum()), "; errors:", int(x.any_error.sum()))
