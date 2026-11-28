"""Cross-match discovery candidates against variable-star catalogues on VizieR (Harvard mirror;
the main CDS site was down on 2026-11-28). VSX here is VizieR's copy (B/vsx), which can lag the live VSX."""
import urllib.request, urllib.parse, sys
stars = {"513211100034794": (99.311093, 12.845841), "435209100016718": (280.891481, -1.135863), "283212300076884": (276.721537, -23.707572)}
cats = {"VSX": "B/vsx/vsx", "Gaia DR3 variables": "I/358/vclassre", "Gaia DR3 var summary": "I/358/varisum",
        "ASAS-SN variables": "II/366/catalog", "ATLAS variables": "J/AJ/156/241/table4", "ZTF CPVS (Chen 2020)": "J/ApJS/249/18/table2"}
for oid, (ra, dec) in stars.items():
    print(f"=== {oid}  ({ra}, {dec})")
    for name, src in cats.items():
        q = urllib.parse.urlencode({"-source": src, "-c": f"{ra} {dec}", "-c.rs": "10", "-out.max": "5", "-out.add": "_r", "-sort": "_r"})
        try:
            txt = urllib.request.urlopen("https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?" + q, timeout=60).read().decode()
        except Exception as ex:
            print(f"  {name:24s} ERROR {ex}"); continue
        rows = [l for l in txt.splitlines() if l and not l.startswith("#")]
        # asu-tsv: header line, units line, dashes line, then data
        data = rows[3:] if len(rows) > 3 else []
        hdr = rows[0] if rows else ""
        print(f"  {name:24s} {len(data)} match(es)" + (f" | {hdr[:150]}" if data else ""))
        for d in data[:2]: print("      ", d[:220])
