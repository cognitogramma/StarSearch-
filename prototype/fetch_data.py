"""Download Gaia DR3 eclipsing-binary G-band light curves for the prototype.

The ESA Gaia archive (gea.esac.esa.int) was showing a "Preparing for Gaia DR4 /
temporarily unavailable" page when this was written (2026-11-27), so this script
uses the UPJŠ TAP mirror, which serves Gaia DR3 epoch photometry for eclipsing
binaries retrieved through the original Gaia DataLink service.

Star selection (deterministic, never looks at the light curves' periodograms):
  * geom_model_reference_level BETWEEN 10 AND 15 (G mag)
  * frequency BETWEEN 0.05 AND 2 (1/d)   -> periods 0.5-20 d, same as the prior
  * 0.1 <= derived_primary_ecl_depth <= 1.5 mag (drops geometric-model artefacts:
    some rows in the catalogue have "depths" of ~20-30 mag)
  * >= 45 usable G-band points (flux_error not null)
  * one star per period bin (0.5-1.5, 1.5-4, 4-10, 10-20 d): the star with the
    most points in each bin.  Gaia's frequency is used ONLY for this binning and
    for the final comparison; it is never seen by the fitting code.

Writes  data/stars.csv  and  data/lc_<source_id>.csv  (obs_time, flux, flux_error).
"""
from pathlib import Path

import numpy as np
import pyvo

TAP_URL = "https://skvo.science.upjs.sk/tap"
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

N_CANDIDATES = 400
MIN_POINTS = 45
PERIOD_BINS = [(0.5, 1.5), (1.5, 4.0), (4.0, 10.0), (10.0, 20.0)]


def main():
    DATA.mkdir(exist_ok=True)
    svc = pyvo.dal.TAPService(TAP_URL)

    cand = svc.run_sync(f"""
        SELECT TOP {N_CANDIDATES} source_id, frequency, frequency_error,
               geom_model_reference_level, derived_primary_ecl_depth, model_type
        FROM gaiadr3_eb.vari_eclipsing_binary_lite
        WHERE geom_model_reference_level BETWEEN 10 AND 15
          AND frequency BETWEEN 0.05 AND 2
          AND derived_primary_ecl_depth BETWEEN 0.1 AND 1.5
        ORDER BY source_id""").to_table()

    ids = ",".join(str(s) for s in cand["source_id"])
    counts = svc.run_sync(f"""
        SELECT source_id, COUNT(*) AS n
        FROM gaiadr3_eb.lightcurves
        WHERE band = 'G' AND flux_error IS NOT NULL AND source_id IN ({ids})
        GROUP BY source_id""").to_table()
    n_by_id = {int(r["source_id"]): int(r["n"]) for r in counts}

    rows = []
    for lo, hi in PERIOD_BINS:
        best = None
        for r in cand:
            sid = int(r["source_id"])
            P = 1.0 / float(r["frequency"])
            n = n_by_id.get(sid, 0)
            if lo <= P < hi and n >= MIN_POINTS and (best is None or n > best[1]):
                best = (r, n)
        if best is None:
            print(f"no star in period bin {lo}-{hi} d")
            continue
        r, n = best
        rows.append(dict(source_id=int(r["source_id"]),
                         gaia_frequency=float(r["frequency"]),
                         gaia_frequency_error=float(r["frequency_error"]),
                         gmag=float(r["geom_model_reference_level"]),
                         primary_depth=float(r["derived_primary_ecl_depth"]),
                         model_type=str(r["model_type"]), n_points=n))

    with open(DATA / "stars.csv", "w") as fh:
        keys = list(rows[0])
        fh.write(",".join(keys) + "\n")
        for row in rows:
            fh.write(",".join(str(row[k]) for k in keys) + "\n")

    for row in rows:
        sid = row["source_id"]
        lc = svc.run_sync(f"""
            SELECT obs_time, flux, flux_error FROM gaiadr3_eb.lightcurves
            WHERE source_id = {sid} AND band = 'G'
              AND flux_error IS NOT NULL AND flux IS NOT NULL
            ORDER BY obs_time""").to_table()
        arr = np.column_stack([np.asarray(lc[c], dtype=float)
                               for c in ("obs_time", "flux", "flux_error")])
        np.savetxt(DATA / f"lc_{sid}.csv", arr, delimiter=",",
                   header="obs_time_bjd_minus_2455197.5,flux_e_per_s,flux_error_e_per_s",
                   comments="", fmt="%.8f")
        print(f"{sid}: {len(arr)} G points, Gaia P = {1/row['gaia_frequency']:.4f} d, "
              f"G = {row['gmag']:.2f}, {row['model_type']}")


if __name__ == "__main__":
    main()
