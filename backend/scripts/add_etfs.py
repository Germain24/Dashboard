"""Ajoute un lot d'ETF UCITS liquides à tickers.csv + ToutBroker.xlsx.

- Secteur 1 = ETF, Secteur 2-5 classés automatiquement (classify_etf_sectors).
- Dispo broker laissée VIDE (= disponible, à corriger à la main par l'utilisateur).
- Dédoublonnage contre l'existant (par ticker).
- Les tickers invalides/illiquides seront écartés au prochain run (financials vides
  -> supprimés ; volume < 100k€/j -> non alloués).
"""
from __future__ import annotations

import pandas as pd

from app.services.finance.buffett.broker_availability import find_broker_file
from app.services.finance.buffett.config import Config
from scripts.classify_etf_sectors import classify

# (ticker Yahoo, nom) — ETF UCITS larges et liquides, par catégorie.
ETFS: list[tuple[str, str]] = [
    # ── Monde / Global actions ────────────────────────────────────────────
    ("IWDA.L", "iShares Core MSCI World UCITS ETF USD (Acc)"),
    ("SWDA.L", "iShares Core MSCI World UCITS ETF USD (Acc)"),
    ("EUNL.DE", "iShares Core MSCI World UCITS ETF USD (Acc)"),
    ("VWCE.DE", "Vanguard FTSE All-World UCITS ETF USD Acc"),
    ("VWRL.L", "Vanguard FTSE All-World UCITS ETF USD Dist"),
    ("VWRP.L", "Vanguard FTSE All-World UCITS ETF USD Acc"),
    ("XDWD.L", "Xtrackers MSCI World UCITS ETF 1C"),
    ("SPPW.DE", "SPDR MSCI World UCITS ETF"),
    ("ISAC.L", "iShares MSCI ACWI UCITS ETF USD (Acc)"),
    ("SSAC.L", "iShares MSCI ACWI UCITS ETF USD (Acc)"),
    ("HMWO.L", "HSBC MSCI World UCITS ETF USD"),
    ("WSML.L", "iShares MSCI World Small Cap UCITS ETF USD (Acc)"),
    ("IWMO.L", "iShares Edge MSCI World Momentum Factor UCITS ETF"),
    ("IWQU.L", "iShares Edge MSCI World Quality Factor UCITS ETF"),
    ("MVOL.L", "iShares Edge MSCI World Minimum Volatility UCITS ETF"),
    ("IWVL.L", "iShares Edge MSCI World Value Factor UCITS ETF USD (Acc)"),
    ("XDEW.DE", "Xtrackers MSCI World ESG UCITS ETF"),
    # ── USA ───────────────────────────────────────────────────────────────
    ("CSPX.L", "iShares Core S&P 500 UCITS ETF USD (Acc)"),
    ("SXR8.DE", "iShares Core S&P 500 UCITS ETF USD (Acc)"),
    ("VUSA.L", "Vanguard S&P 500 UCITS ETF USD Dist"),
    ("VUAA.L", "Vanguard S&P 500 UCITS ETF USD Acc"),
    ("IUSA.L", "iShares Core S&P 500 UCITS ETF USD Dist"),
    ("SPY5.L", "SPDR S&P 500 UCITS ETF"),
    ("CSP1.L", "iShares Core S&P 500 UCITS ETF USD (Acc)"),
    ("EQQQ.L", "Invesco EQQQ Nasdaq-100 UCITS ETF"),
    ("CNDX.L", "iShares Nasdaq 100 UCITS ETF USD (Acc)"),
    ("SXRV.DE", "iShares Nasdaq 100 UCITS ETF (Acc)"),
    ("CSUS.L", "iShares MSCI USA UCITS ETF"),
    ("IUSQ.L", "iShares MSCI USA UCITS ETF USD (Acc)"),
    ("IUVL.L", "iShares Edge MSCI USA Value Factor UCITS ETF"),
    ("XRSG.DE", "Xtrackers Russell 2000 UCITS ETF"),
    ("ZPRR.DE", "SPDR Russell 2000 US Small Cap UCITS ETF"),
    ("FUSD.L", "Fidelity US Quality Income UCITS ETF"),
    # ── Europe / Eurozone ─────────────────────────────────────────────────
    ("IMEU.L", "iShares Core MSCI Europe UCITS ETF EUR (Acc)"),
    ("SMEA.L", "iShares Core MSCI Europe UCITS ETF EUR (Acc)"),
    ("VEUR.L", "Vanguard FTSE Developed Europe UCITS ETF Dist"),
    ("VERX.L", "Vanguard FTSE Developed Europe ex UK UCITS ETF"),
    ("EXSA.DE", "iShares STOXX Europe 600 UCITS ETF (DE)"),
    ("MEUD.PA", "Amundi Core Stoxx Europe 600 UCITS ETF Acc"),
    ("CSEMU.L", "iShares Core MSCI EMU UCITS ETF EUR (Acc)"),
    ("SX5S.DE", "iShares Core EURO STOXX 50 UCITS ETF"),
    ("XD5E.DE", "Xtrackers EURO STOXX 50 UCITS ETF"),
    # ── Émergents ─────────────────────────────────────────────────────────
    ("EIMI.L", "iShares Core MSCI EM IMI UCITS ETF USD (Acc)"),
    ("EMIM.L", "iShares Core MSCI EM IMI UCITS ETF USD (Acc)"),
    ("IEMA.L", "iShares MSCI EM UCITS ETF USD (Acc)"),
    ("VFEM.L", "Vanguard FTSE Emerging Markets UCITS ETF USD Dist"),
    ("AEEM.PA", "Amundi MSCI Emerging Markets UCITS ETF"),
    ("XMME.DE", "Xtrackers MSCI Emerging Markets UCITS ETF 1C"),
    # ── Japon / Asie / pays ───────────────────────────────────────────────
    ("SJPA.L", "iShares Core MSCI Japan IMI UCITS ETF USD (Acc)"),
    ("IJPN.L", "iShares MSCI Japan UCITS ETF USD (Dist)"),
    ("VJPN.L", "Vanguard FTSE Japan UCITS ETF USD Dist"),
    ("CPXJ.L", "iShares Core MSCI Pacific ex Japan UCITS ETF"),
    ("NDIA.L", "iShares MSCI India UCITS ETF USD Acc"),
    ("FXC.L", "iShares China Large Cap UCITS ETF"),
    ("HMCH.L", "HSBC MSCI China UCITS ETF"),
    # ── Obligations souveraines (DÉFENSIF) ────────────────────────────────
    ("IBGE.L", "iShares € Govt Bond 0-1yr UCITS ETF"),
    ("IBGX.L", "iShares € Govt Bond 1-3yr UCITS ETF"),
    ("IEGA.L", "iShares Core € Govt Bond UCITS ETF EUR (Dist)"),
    ("SEGA.L", "iShares Core € Govt Bond UCITS ETF EUR (Dist)"),
    ("VETY.L", "Vanguard EUR Eurozone Government Bond UCITS ETF"),
    ("IBTS.L", "iShares $ Treasury Bond 1-3yr UCITS ETF"),
    ("IBTM.L", "iShares $ Treasury Bond 7-10yr UCITS ETF USD (Dist)"),
    ("IDTL.L", "iShares $ Treasury Bond 20+yr UCITS ETF"),
    ("IGLO.L", "iShares Global Government Bond UCITS ETF"),
    ("IGLT.L", "iShares Core UK Gilts UCITS ETF"),
    ("IBCI.L", "iShares € Inflation Linked Govt Bond UCITS ETF EUR (Acc)"),
    ("ITPS.L", "iShares $ TIPS UCITS ETF USD (Acc)"),
    # ── Obligations corporate / agrégat / high yield ──────────────────────
    ("IEAC.L", "iShares Core € Corp Bond UCITS ETF EUR (Dist)"),
    ("LQDE.L", "iShares $ Corp Bond UCITS ETF USD (Dist)"),
    ("VECP.L", "Vanguard EUR Corporate Bond UCITS ETF"),
    ("EUNA.DE", "iShares Core € Aggregate Bond UCITS ETF"),
    ("AGGG.L", "iShares Core Global Aggregate Bond UCITS ETF"),
    ("VAGF.L", "Vanguard Global Aggregate Bond UCITS ETF EUR Hedged"),
    ("IHYG.L", "iShares € High Yield Corp Bond UCITS ETF EUR (Dist)"),
    ("IHYU.L", "iShares $ High Yield Corp Bond UCITS ETF"),
    ("SLXX.L", "iShares Core £ Corp Bond UCITS ETF"),
    # ── Or / matières premières ───────────────────────────────────────────
    ("SGLN.L", "iShares Physical Gold ETC"),
    ("PHAU.L", "WisdomTree Physical Gold"),
    ("4GLD.DE", "Xetra-Gold"),
    ("SSLN.L", "iShares Physical Silver ETC"),
    ("IPLT.L", "iShares Physical Platinum ETC"),
    ("ICOM.L", "iShares Diversified Commodity Swap UCITS ETF"),
    ("CMOD.L", "Invesco Bloomberg Commodity UCITS ETF"),
    # ── Secteurs mondiaux ─────────────────────────────────────────────────
    ("XDWT.L", "Xtrackers MSCI World Information Technology UCITS ETF"),
    ("WHEA.L", "iShares MSCI World Health Care Sector UCITS ETF"),
    ("WNRG.L", "iShares MSCI World Energy Sector UCITS ETF"),
    ("WFIN.L", "iShares MSCI World Financials Sector UCITS ETF"),
    ("2B7K.DE", "iShares MSCI World Consumer Staples Sector UCITS ETF"),
    # ── Thématiques / dividendes ──────────────────────────────────────────
    ("VHYL.L", "Vanguard FTSE All-World High Dividend Yield UCITS ETF"),
    ("ISPA.DE", "iShares STOXX Global Select Dividend 100 UCITS ETF (DE)"),
    ("IUKD.L", "iShares UK Dividend UCITS ETF"),
    ("INRG.L", "iShares Global Clean Energy UCITS ETF USD (Dist)"),
    ("RBOT.L", "iShares Automation & Robotics UCITS ETF"),
    ("WCBR.L", "WisdomTree Cybersecurity UCITS ETF"),
    ("DGTL.L", "iShares Digitalisation UCITS ETF"),
]


def main(write: bool = True) -> None:
    tk_path = Config.TICKERS_CSV
    bf = find_broker_file()
    tdf = pd.read_csv(tk_path)
    tcol_csv = tdf.columns[0]
    existing_csv = set(tdf[tcol_csv].astype(str).str.strip().str.upper())

    bdf = pd.read_excel(bf)
    tcol_b = [c for c in bdf.columns if "ticker" in c.lower()][0]
    existing_b = set(bdf[tcol_b].astype(str).str.strip().str.upper())

    new = [(t, n) for t, n in ETFS if t.upper() not in existing_b and t.upper() not in existing_csv]
    print(f"{len(ETFS)} ETF candidats | {len(new)} nouveaux (le reste déjà présent)")

    rows = []
    for t, nom in new:
        s2, s3, s4, s5 = classify(nom)
        row = {c: None for c in bdf.columns}
        row[tcol_b] = t
        row["Nom"] = nom
        row["Secteur 1"] = "ETF"
        for i, v in zip(range(2, 6), (s2, s3, s4, s5)):
            col = next((c for c in bdf.columns if str(c).strip().lower() == f"secteur {i}"), None)
            if col:
                row[col] = v
        rows.append(row)
        print(f"  + {t:10} {s2} > {s3} > {s4}")

    if write and rows:
        bdf2 = pd.concat([bdf, pd.DataFrame(rows)], ignore_index=True)
        bdf2.to_excel(bf, index=False)
        add_csv = pd.DataFrame({tcol_csv: [t for t, _ in new]})
        tdf2 = pd.concat([tdf, add_csv], ignore_index=True)
        tdf2.to_csv(tk_path, index=False)
        print(f"\n[OK] {len(rows)} ETF ajoutés à ToutBroker.xlsx et tickers.csv.")
        try:
            from app.services.finance.buffett.broker_availability import reset_etf_cache
            reset_etf_cache()
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    main(write="--dry" not in sys.argv)
