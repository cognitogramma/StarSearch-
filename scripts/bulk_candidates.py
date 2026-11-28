"""Second stage of the bulk scan: analyse every strong, uncatalogued signal saved by
bulk_scan.py (results/bulk/candidates/*.npz).

  stage "mh"     full periodogram-guided MH (3 chains x 3000 steps) + artefact flags
                 -> results/bulk_candidates_mh.csv
  stage "xmatch" for candidates that pass the flags: VizieR (Harvard mirror) cross-match
                 against VSX, Gaia DR3 variability, ASAS-SN, ATLAS, plus Gaia DR3 neighbours
                 within 4" (how much light could come from another star)
                 -> results/bulk_candidates_xmatch.csv
  stage "grade"  automatic grade + folded light curves for grade A -> results/bulk_shortlist.csv

Usage: python scripts/bulk_candidates.py mh|xmatch|grade [max_seconds]
Every stage is resumable and stops cleanly after max_seconds (default 6000).
"""
import glob, os, sys, time, urllib.parse, urllib.request
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve
from starsearch.sampler import analyse

SYN, SID, YEAR = 29.530589, 27.321662, 365.25
PRI_LOG_BF, PRI_MAG = 50, 19.5
MH_OUT, XM_OUT, SHORT = "results/bulk_candidates_mh.csv", "results/bulk_candidates_xmatch.csv", "results/bulk_shortlist.csv"
MIRROR = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?"
CATS = {"vsx": ("B/vsx/vsx", ["Name", "Type", "Period"]), "gaia_dr3_var": ("I/358/vclassre", ["Source", "Class"]),
        "asassn": ("II/366/catalog", ["ID", "Type", "Per"]), "atlas": ("J/AJ/156/241/table4", ["ATOID", "Class"])}


def calendar_flags(f, mag):
    out = []
    if any(abs(f - k) < 0.02 * k for k in (1, 2, 3)) or abs(f - 1.0027379) < 0.01:
        out.append("daily")
    moon = [1 / SYN, 1 / SID] + [k + s / SYN for k in (1, 2, 1.0027379) for s in (-1, 1)]
    if any(abs(f - m) < 0.003 for m in moon) or any(abs(f - k / SYN) < 0.003 for k in (2, 3)):
        out.append("lunar")
    if f < 3 / YEAR:
        out.append("annual")
    if mag > 20.5:
        out.append("faint")
    return out


def mh_one(path):
    oid = int(os.path.basename(path).split(".")[0])
    z = np.load(path)
    t, y, e = z["t"], z["y"], z["e"]
    try:
        lc = LightCurve(t, y, e, K=3, f_max=10.0)
        r = analyse(lc, np.random.default_rng(oid % 2**32), n_chains=3, n_steps=3000, burn=600)
    except Exception as ex:
        return dict(oid=oid, status=f"error:{type(ex).__name__}")
    theta, model = lc.best_fit(r["f1"])
    amp = float(np.percentile(model, 95) - np.percentile(model, 5))
    mag = float(np.median(y))
    flags = calendar_flags(r["f1"], mag)
    if r["p1"] < 0.9: flags.append("weak")
    if r["rhat"] > 1.1: flags.append("rhat")
    return dict(oid=oid, status="ok", ra=float(z["ra"]), dec=float(z["dec"]), mag=mag, N=len(t), T=lc.T,
                P1=1 / r["f1"], p1=r["p1"], P1_sd=r["sd1"] / r["f1"] ** 2,
                P2=1 / r["f2"] if np.isfinite(r["f2"]) and r["f2"] > 0 else np.nan, p2=r["p2"],
                amp=amp, log_bf=r["log_bf"], rhat=r["rhat"], noise_scale=r["noise_scale"],
                flags=";".join(flags) or "clean")


def strict_selection():
    """Second, stricter screen on the bulk score tables (results/bulk/*.parquet).
    The first screen let through two artefact families that dominate crowded fields:
    periods within ~5% of a day (and its harmonics) and seasonal periods (40-180 d).
    Keep: FAP < 1e-10, log Bayes factor > 20, amplitude >= 0.05 mag, 0.1 d < P < 30 d,
    frequency not within 5% of 1, 2 or 3 cycles/day, not on a lunar beat, not in the catalogue."""
    tabs = [pd.read_parquet(f) for f in sorted(glob.glob("results/bulk/*.parquet"))]
    d = pd.concat(tabs, ignore_index=True).drop_duplicates("oid")
    f = d.f
    near_day = np.zeros(len(d), bool)
    for k in (1, 2, 3):
        near_day |= np.abs(f - k) < 0.05 * k
    moon = np.zeros(len(d), bool)
    for m in [k + s_ / SYN for k in (1, 2, 1.0027379) for s_ in (-1, 1)]:
        moon |= np.abs(f - m) < 0.005
    keep = ((d.fap < 1e-10) & (d.log_bf > 20) & (d.amp >= 0.05) & (f > 1 / 30) & (f < 10)
            & ~near_day & ~moon & ~d.in_catalog)
    return d, set(d.oid[keep])


def stage_mh(deadline):
    done = set(pd.read_csv(MH_OUT).oid) if os.path.exists(MH_OUT) else set()
    d, sel = strict_selection()
    # priority tier (the run of 28 Nov 2026): strongest signals in stars brighter than r = 19.5
    pri = d[d.oid.isin(sel) & (d.log_bf > PRI_LOG_BF) & (d.mag < PRI_MAG)]
    sel = set(pri.oid)
    print(f"strict screen: {len(d[d.oid.isin(set(d.oid))])} scored; priority tier: {len(sel)}", flush=True)
    paths = [p for p in sorted(glob.glob("results/bulk/candidates/*.npz"))
             if int(os.path.basename(p)[:-4]) in sel and int(os.path.basename(p)[:-4]) not in done]
    print(len(done), "done,", len(paths), "to go", flush=True)
    buf = []
    with mp.Pool(os.cpu_count()) as pool:
        for i, r in enumerate(pool.imap_unordered(mh_one, paths, chunksize=4), 1):
            buf.append(r)
            if len(buf) >= 200 or i == len(paths) or time.time() > deadline:
                pd.DataFrame(buf).to_csv(MH_OUT, mode="a", header=not os.path.exists(MH_OUT), index=False); buf = []
                print(i, flush=True)
                if time.time() > deadline:
                    pool.terminate(); print("stopping at the time limit; rerun to continue", flush=True); return


def vizier(src, ra, dec, rad, cols="", nmax=3):
    q = {"-source": src, "-c": f"{ra} {dec}", "-c.rs": str(rad), "-out.max": str(nmax), "-out.add": "_r", "-sort": "_r"}
    if cols: q["-out"] = cols
    else: q["-out.all"] = ""
    for attempt in range(3):
        try:
            txt = urllib.request.urlopen(MIRROR + urllib.parse.urlencode(q), timeout=90).read().decode()
            L = [l.split("\t") for l in txt.splitlines() if l and not l.startswith("#")]
            return [dict(zip(L[0], v)) for v in L[3:]] if len(L) > 3 else []
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def xm_one(row):
    out = {"oid": row.oid}
    for k, (src, cols) in CATS.items():
        m = vizier(src, row.ra, row.dec, 10, nmax=1)
        out[k] = "error" if m is None else ("" if not m else f"{float(m[0].get('_r', 'nan')):.1f}\" " +
                                                 " | ".join(m[0].get(c, "").strip() for c in cols if m[0].get(c, "").strip()))
    g = vizier("I/355/gaiadr3", row.ra, row.dec, 4, cols="Source,Gmag,Plx,e_Plx,RUWE", nmax=20)
    if g is None:
        out["gaia_source"] = "error"
    elif g:
        mags = [(float(s["_r"]), float(s["Gmag"])) for s in g if s.get("Gmag", "").strip()]
        if mags:
            flux = [10 ** (-0.4 * m) for _, m in mags]
            out.update(gaia_source=g[0].get("Source", ""), G=mags[0][1], plx=g[0].get("Plx", ""), e_plx=g[0].get("e_Plx", ""),
                       ruwe=g[0].get("RUWE", ""), gaia_sep=mags[0][0], neighbour_light=sum(flux[1:]) / sum(flux))
    return out


def stage_xmatch(deadline):
    mh = pd.read_csv(MH_OUT)
    mh = mh[(mh.status == "ok") & (mh["flags"] == "clean")]
    done = set(pd.read_csv(XM_OUT).oid) if os.path.exists(XM_OUT) else set()
    todo = [r for r in mh.itertuples() if r.oid not in done]
    print(len(done), "done,", len(todo), "to go", flush=True)
    for s0 in range(0, len(todo), 60):
        if time.time() > deadline:
            print("stopping at the time limit; rerun to continue", flush=True); return
        with ThreadPoolExecutor(3) as ex:
            res = list(ex.map(xm_one, todo[s0:s0 + 60]))
        pd.DataFrame(res).to_csv(XM_OUT, mode="a", header=not os.path.exists(XM_OUT), index=False)
        print(s0 + len(res), flush=True)


def stage_grade():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    mh = pd.read_csv(MH_OUT); xm = pd.read_csv(XM_OUT)
    d = mh.merge(xm, on="oid").fillna({k: "" for k in CATS})
    d["catalogued"] = d[list(CATS)].astype(str).apply(lambda s: s.str.len() > 0).any(axis=1)
    depth = 1 - 10 ** (-0.4 * d.amp)                         # fractional dip / swing in flux
    nl = pd.to_numeric(d.get("neighbour_light"), errors="coerce").fillna(0)
    d["neighbour_can_fake"] = nl >= depth                    # a neighbour fully vanishing could fake it
    sep = pd.to_numeric(d.get("gaia_sep"), errors="coerce")
    d["grade"] = "C"
    b = ~d.catalogued & ~d.neighbour_can_fake & (sep < 1.0)
    d.loc[b, "grade"] = "B"
    a = b & (d.mag < 19.5) & (d.log_bf > 50) & (d.p1 > 0.99) & (nl < depth / 2)
    d.loc[a, "grade"] = "A"
    d.loc[d.catalogued, "grade"] = "known"
    d = d.sort_values(["grade", "log_bf"], ascending=[True, False])
    d.to_csv(SHORT, index=False)
    os.makedirs("figs/bulk_candidates", exist_ok=True)
    for r in d[d.grade == "A"].itertuples():
        z = np.load(f"results/bulk/candidates/{r.oid}.npz")
        ph = ((z["t"] - z["t"].min()) / r.P1) % 1
        fig, ax = plt.subplots(figsize=(7, 3.4))
        ax.scatter(np.r_[ph, ph + 1], np.r_[z["y"], z["y"]], s=4, color="#2a78d6", alpha=0.55)
        ax.invert_yaxis(); ax.set_xlabel("phase"); ax.set_ylabel("r mag"); ax.spines[["top", "right"]].set_visible(False)
        ax.set_title(f"ZTF {r.oid}: P = {r.P1:.5f} d, r = {r.mag:.1f}, amp {r.amp:.2f}", fontsize=11, loc="left")
        fig.savefig(f"figs/bulk_candidates/{r.oid}.png", dpi=130, bbox_inches="tight"); plt.close(fig)
    print(d.grade.value_counts().to_dict())


if __name__ == "__main__":
    stage = sys.argv[1]
    deadline = time.time() + (float(sys.argv[2]) if len(sys.argv) > 2 else 6000)
    {"mh": lambda: stage_mh(deadline), "xmatch": lambda: stage_xmatch(deadline), "grade": stage_grade}[stage]()
