"""For each final candidate, list every VizieR catalogue with a source within 2" and flag
those whose title mentions variability (variable, eclipsing, periodic, OGLE, VVV, light curve...).
Writes results/bulk_final_allcats.csv."""
import re, html, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

KEY = re.compile(r"variab|eclips|period|ogle|vvv|light.?curve|pulsat|rr lyr|cepheid|delta sc|binar|ztf|atlas|asas|kepler|tess|gaia dr3.*var", re.I)


def cats_at(ra, dec, rad=2):
    url = (f"https://vizier.cfa.harvard.edu/viz-bin/VizieR-2?-c={ra:.6f}%20{dec:+.6f}&-c.rs={rad}&-out.max=1&-meta.foot&-meta.ucd=0")
    for attempt in range(3):
        try:
            t = urllib.request.urlopen(url, timeout=240).read().decode(errors="ignore")
            break
        except Exception:
            time.sleep(5)
    else:
        return None
    txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    hits = []
    for m in re.finditer(r"\b((?:[IVX]+|[BJ])/[A-Za-z0-9+/._-]+)\s+\d+\s+\(density[^)]*\)\s+\(c\)\s+\S+\s+\S+\s+(.{0,120}?)\s+ReadMe", txt):
        hits.append((m.group(1), m.group(2).strip()))
    return hits


c = pd.read_csv("results/bulk_final_candidates.csv")
c = c[c.eye == "convincing"]
ra_dec = [(r.oid, *map(float, (0, 0))) for r in c.itertuples()]
x = pd.read_csv("results/bulk_shortlist_final.csv").set_index("oid")
def one(oid):
    hits = cats_at(x.loc[oid, "ra"], x.loc[oid, "dec"])
    if hits is None:
        return dict(oid=oid, n_catalogues="error", variability_catalogues="error")
    var = [f"{cid}: {title}" for cid, title in hits if KEY.search(title)]
    return dict(oid=oid, n_catalogues=len(hits), variability_catalogues=" || ".join(var))
with ThreadPoolExecutor(2) as ex:
    res = list(ex.map(one, c.oid))
out = pd.DataFrame(res); out.to_csv("results/bulk_final_allcats.csv", index=False)
pd.set_option("display.max_colwidth", 200)
print(out.to_string(index=False))
