"""Feuille ``ETF_Pays`` par TABLE D'INDICES curée (fiable, sans scraping).

Chaque ETF est mappé à un indice via sa colonne Secteur 4 (région) :
- mono-pays (France, USA, Japon…) -> 100 % ce pays ;
- région large (Monde, Europe, Zone euro, Émergents…) -> répartition pays standard
  de l'indice de référence (poids publics, stables).
Les ETF sectoriels/thématiques gardent la région de leur indice (le cap pays les
exemptera côté optimiseur). Les obligations : pays = région de l'émetteur.

Les répartitions sont approximatives (sources MSCI/STOXX) et à affiner à la main.
"""
from __future__ import annotations

import pandas as pd

from app.services.finance.buffett.broker_availability import find_broker_file

# Répartition pays (%) par région de référence (≈ indices standards).
REGION_COUNTRIES: dict[str, dict[str, float]] = {
    "Monde": {"United States": 70, "Japan": 6, "United Kingdom": 4, "Canada": 3,
              "France": 3, "Switzerland": 3, "Germany": 2.5, "Australia": 2,
              "Netherlands": 1.5, "Other": 4.5},
    "USA": {"United States": 100},
    "Zone euro": {"France": 36, "Germany": 27, "Netherlands": 14, "Italy": 8,
                  "Spain": 7, "Finland": 3, "Belgium": 3, "Ireland": 2},
    "Europe": {"United Kingdom": 23, "France": 17, "Switzerland": 15, "Germany": 14,
               "Netherlands": 7, "Sweden": 5, "Italy": 5, "Spain": 5, "Denmark": 5,
               "Other": 4},
    "Émergents": {"China": 28, "India": 18, "Taiwan": 18, "South Korea": 12,
                  "Brazil": 5, "Saudi Arabia": 4, "South Africa": 3, "Mexico": 2,
                  "Other": 10},
    "Asie émergente": {"China": 38, "India": 22, "Taiwan": 22, "South Korea": 14,
                       "Other": 4},
    "Émergents EMEA": {"Saudi Arabia": 30, "South Africa": 22, "United Arab Emirates": 12,
                       "Poland": 10, "Qatar": 8, "Other": 18},
    "Amérique latine": {"Brazil": 58, "Mexico": 27, "Chile": 7, "Other": 8},
    "Asie-Pacifique": {"Australia": 33, "Taiwan": 22, "South Korea": 15, "Hong Kong": 12,
                       "Singapore": 9, "Other": 9},
    # mono-pays (région == pays)
    "France": {"France": 100}, "Allemagne": {"Germany": 100}, "Italie": {"Italy": 100},
    "Espagne": {"Spain": 100}, "Autriche": {"Austria": 100}, "Japon": {"Japan": 100},
    "Inde": {"India": 100}, "Chine": {"China": 100}, "Brésil": {"Brazil": 100},
    "Grèce": {"Greece": 100}, "Pologne": {"Poland": 100}, "Royaume-Uni": {"United Kingdom": 100},
}


def main() -> None:
    import json
    from pathlib import Path
    bf = find_broker_file()
    b = pd.read_excel(bf)
    tcol = [c for c in b.columns if "ticker" in c.lower()][0]
    etfs = b[b["Secteur 1"].astype(str).str.strip().str.upper() == "ETF"].copy()

    # Données réelles justETF déjà récupérées (cache) -> priorité sur la table curée.
    cache = {}
    cp = Path(__file__).parent / ".etf_lookthrough_cache.json"
    if cp.exists():
        cache = json.loads(cp.read_text())
    n_real = 0

    rows, unmapped = [], []
    for _, r in etfs.iterrows():
        t = str(r[tcol]).strip()
        s4 = str(r.get("Secteur 4", "")).strip()
        nom = str(r.get("Nom", ""))
        s5 = str(r.get("Secteur 5", "")).strip()
        real = (cache.get(t) or {}).get("pays")
        if real:                       # vraie répartition justETF
            cc = real
            n_real += 1
            src = "justETF"
        else:                          # table d'indices curée (région en Secteur 4, sinon 5)
            cc = REGION_COUNTRIES.get(s4) or REGION_COUNTRIES.get(s5)
            if cc is None:
                unmapped.append((t, s4 or s5))
                cc = {}
            src = "curé"
        rows.append({"Ticker": t, "Nom": nom, "Region": s4, "Source": src, **cc})

    df = pd.DataFrame(rows).fillna(0)
    fixed = ["Ticker", "Nom", "Region", "Source"]
    cols = [c for c in df.columns if c not in fixed]
    cols = sorted(cols, key=lambda c: df[c].sum(), reverse=True)
    df = df[fixed + cols]

    with pd.ExcelWriter(bf, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        df.to_excel(w, sheet_name="ETF_Pays", index=False)

    print(f"[OK] ETF_Pays : {len(df)} ETF, {len(cols)} pays | "
          f"{n_real} via justETF (réel), {len(df)-n_real} via table curée")
    if unmapped:
        from collections import Counter
        print("  régions non mappées (curé):", dict(Counter(s for _, s in unmapped)))
    if unmapped:
        from collections import Counter
        print("  régions non mappées:", dict(Counter(s for _, s in unmapped)))


if __name__ == "__main__":
    main()
