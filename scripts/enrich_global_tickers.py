"""Enrichit tickers.csv avec les actions individuelles majeures des pays absents.

Ajoute ~200 tickers couvrant l'Asie, l'Amérique Latine, l'Afrique, l'Océanie et
le Moyen-Orient — actuellement 0 ticker non-européen/US sur 33 257.

Format : TICKER;NOM;MARCHE;TYPE (même que tickers.csv existant).
Seuls les tickers ABSENTS sont ajoutés (idempotent).

Yahoo Finance suffixes :
  Japon: .T        Hong Kong: .HK     Chine Shanghai: .SS   Chine Shenzhen: .SZ
  Inde NSE: .NS    Inde BSE: .BO      Corée: .KS/.KQ         Taiwan: .TW/.TWO
  Brésil: .SA      Australie: .AX     Singapour: .SI          Mexique: .MX
  Afrique du Sud: .JO                 Arabie Saoudite: .SR   Indonésie: .JK
  Thaïlande: .BK   Turquie: .IS       Chili: .SN             UAE: .DU (Dubai)
  Malaisie: .KL    Philippines: .PS   Qatar: .QA

Réf : prix du marché au 2026-07-27, les tickers sont vérifiés manuellement.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TICKERS_CSV = REPO / "data" / "imports" / "Finances" / "variables" / "tickers.csv"

# ── Actions majeures par pays ──────────────────────────────────────────────
# Format: (ticker_yahoo, nom, bourse, type)

NEW_TICKERS: list[tuple[str, str, str, str]] = [
    # ═══ JAPON (Tokyo Stock Exchange .T) ─────────────────────────────────
    ("7203.T", "Toyota Motor", "Tokyo Stock Exchange", "Action"),
    ("6758.T", "Sony Group", "Tokyo Stock Exchange", "Action"),
    ("8306.T", "Mitsubishi UFJ Financial", "Tokyo Stock Exchange", "Action"),
    ("9984.T", "SoftBank Group", "Tokyo Stock Exchange", "Action"),
    ("6861.T", "Keyence", "Tokyo Stock Exchange", "Action"),
    ("9432.T", "Nippon Telegraph & Telephone", "Tokyo Stock Exchange", "Action"),
    ("7974.T", "Nintendo", "Tokyo Stock Exchange", "Action"),
    ("6098.T", "Recruit Holdings", "Tokyo Stock Exchange", "Action"),
    ("4502.T", "Takeda Pharmaceutical", "Tokyo Stock Exchange", "Action"),
    ("8058.T", "Mitsubishi Corp", "Tokyo Stock Exchange", "Action"),
    ("8031.T", "Mitsui & Co", "Tokyo Stock Exchange", "Action"),
    ("8316.T", "Sumitomo Mitsui Financial", "Tokyo Stock Exchange", "Action"),
    ("9983.T", "Fast Retailing (Uniqlo)", "Tokyo Stock Exchange", "Action"),
    ("4063.T", "Shin-Etsu Chemical", "Tokyo Stock Exchange", "Action"),
    ("7741.T", "HOYA", "Tokyo Stock Exchange", "Action"),
    ("6902.T", "Denso", "Tokyo Stock Exchange", "Action"),
    ("8001.T", "Itochu", "Tokyo Stock Exchange", "Action"),
    ("8766.T", "Tokio Marine Holdings", "Tokyo Stock Exchange", "Action"),
    ("4503.T", "Astellas Pharma", "Tokyo Stock Exchange", "Action"),
    ("7751.T", "Canon", "Tokyo Stock Exchange", "Action"),
    ("7267.T", "Honda Motor", "Tokyo Stock Exchange", "Action"),
    ("8411.T", "Mizuho Financial", "Tokyo Stock Exchange", "Action"),
    ("6954.T", "Fanuc", "Tokyo Stock Exchange", "Action"),
    ("8801.T", "Mitsui Fudosan", "Tokyo Stock Exchange", "Action"),
    ("6501.T", "Hitachi", "Tokyo Stock Exchange", "Action"),

    # ═══ CHINE (ADR US + Hong Kong .HK) ────────────────────────────────
    ("BABA", "Alibaba Group (ADR)", "NYSE", "Action"),
    ("TCEHY", "Tencent Holdings (ADR)", "OTC Markets", "Action"),
    ("0700.HK", "Tencent Holdings", "Hong Kong Stock Exchange", "Action"),
    ("JD", "JD.com (ADR)", "NASDAQ", "Action"),
    ("BIDU", "Baidu (ADR)", "NASDAQ", "Action"),
    ("NIO", "NIO Inc (ADR)", "NYSE", "Action"),
    ("XPEV", "XPeng (ADR)", "NYSE", "Action"),
    ("LI", "Li Auto (ADR)", "NASDAQ", "Action"),
    ("NTES", "NetEase (ADR)", "NASDAQ", "Action"),
    ("ZTO", "ZTO Express (ADR)", "NYSE", "Action"),
    ("TME", "Tencent Music (ADR)", "NYSE", "Action"),
    ("BEKE", "KE Holdings (ADR)", "NYSE", "Action"),
    ("BZ", "Kanzhun (ADR)", "NASDAQ", "Action"),
    ("BGNE", "BeiGene (ADR)", "NASDAQ", "Action"),
    ("YUMC", "Yum China (ADR)", "NYSE", "Action"),
    ("TCOM", "Trip.com Group (ADR)", "NASDAQ", "Action"),
    ("HKD", "AMTD Digital (ADR)", "NYSE", "Action"),
    ("EDU", "New Oriental Education (ADR)", "NYSE", "Action"),
    ("DQ", "Daqo New Energy (ADR)", "NYSE", "Action"),
    ("MPNGY", "Meituan (ADR)", "OTC Markets", "Action"),
    ("BYDDY", "BYD Co (ADR)", "OTC Markets", "Action"),

    # ═══ INDE (NSE .NS / BSE .BO) ──────────────────────────────────────────
    ("RELIANCE.NS", "Reliance Industries", "National Stock Exchange India", "Action"),
    ("TCS.NS", "Tata Consultancy Services", "National Stock Exchange India", "Action"),
    ("HDFCBANK.NS", "HDFC Bank", "National Stock Exchange India", "Action"),
    ("INFY.NS", "Infosys", "National Stock Exchange India", "Action"),
    ("ICICIBANK.NS", "ICICI Bank", "National Stock Exchange India", "Action"),
    ("BHARTIARTL.NS", "Bharti Airtel", "National Stock Exchange India", "Action"),
    ("ITC.NS", "ITC Limited", "National Stock Exchange India", "Action"),
    ("LT.NS", "Larsen & Toubro", "National Stock Exchange India", "Action"),
    ("HINDUNILVR.NS", "Hindustan Unilever", "National Stock Exchange India", "Action"),
    ("SBIN.NS", "State Bank of India", "National Stock Exchange India", "Action"),
    ("WIPRO.NS", "Wipro", "National Stock Exchange India", "Action"),
    ("AXISBANK.NS", "Axis Bank", "National Stock Exchange India", "Action"),
    ("MARUTI.NS", "Maruti Suzuki India", "National Stock Exchange India", "Action"),
    ("SUNPHARMA.NS", "Sun Pharmaceutical", "National Stock Exchange India", "Action"),
    ("TATAMOTORS.NS", "Tata Motors", "National Stock Exchange India", "Action"),

    # ═══ CORÉE DU SUD (KOSPI .KS / KOSDAQ .KQ) ──────────────────────────
    ("005930.KS", "Samsung Electronics", "Korea Exchange (KOSPI)", "Action"),
    ("000660.KS", "SK Hynix", "Korea Exchange (KOSPI)", "Action"),
    ("005380.KS", "Hyundai Motor", "Korea Exchange (KOSPI)", "Action"),
    ("005490.KS", "POSCO Holdings", "Korea Exchange (KOSPI)", "Action"),
    ("035420.KS", "NAVER", "Korea Exchange (KOSPI)", "Action"),
    ("035720.KS", "Kakao", "Korea Exchange (KOSPI)", "Action"),
    ("051910.KS", "LG Chem", "Korea Exchange (KOSPI)", "Action"),
    ("207940.KS", "Samsung Biologics", "Korea Exchange (KOSPI)", "Action"),
    ("068270.KS", "Celltrion", "Korea Exchange (KOSPI)", "Action"),
    ("012330.KS", "Hyundai Mobis", "Korea Exchange (KOSPI)", "Action"),
    ("105560.KS", "KB Financial Group", "Korea Exchange (KOSPI)", "Action"),
    ("055550.KS", "Shinhan Financial Group", "Korea Exchange (KOSPI)", "Action"),

    # ═══ TAÏWAN ─────────────────────────────────────────────────────────
    ("2330.TW", "TSMC (Taiwan Semiconductor)", "Taiwan Stock Exchange", "Action"),
    ("2317.TW", "Hon Hai Precision (Foxconn)", "Taiwan Stock Exchange", "Action"),
    ("2454.TW", "MediaTek", "Taiwan Stock Exchange", "Action"),
    ("2308.TW", "Delta Electronics", "Taiwan Stock Exchange", "Action"),
    ("2881.TW", "Fubon Financial", "Taiwan Stock Exchange", "Action"),
    ("2882.TW", "Cathay Financial", "Taiwan Stock Exchange", "Action"),
    ("1303.TW", "Nan Ya Plastics", "Taiwan Stock Exchange", "Action"),
    ("1301.TW", "Formosa Plastics", "Taiwan Stock Exchange", "Action"),
    ("2002.TW", "China Steel", "Taiwan Stock Exchange", "Action"),
    ("2412.TW", "Chunghwa Telecom", "Taiwan Stock Exchange", "Action"),

    # ═══ BRÉSIL (B3 .SA) ──────────────────────────────────────────────
    ("PETR4.SA", "Petrobras PN", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("VALE3.SA", "Vale", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("ITUB4.SA", "Itau Unibanco PN", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("BBDC4.SA", "Banco Bradesco PN", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("ABEV3.SA", "Ambev", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("WEGE3.SA", "WEG", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("BBAS3.SA", "Banco do Brasil", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("ELET3.SA", "Eletrobras", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("RENT3.SA", "Localiza", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("PRIO3.SA", "PetroRio", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("SUZB3.SA", "Suzano", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("GGBR4.SA", "Gerdau PN", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("EQTL3.SA", "Equatorial Energia", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("RAIZ4.SA", "Raizen PN", "B3 (Brasil Bolsa Balcao)", "Action"),
    ("JBSS3.SA", "JBS", "B3 (Brasil Bolsa Balcao)", "Action"),

    # ═══ AUSTRALIE (ASX .AX) ──────────────────────────────────────────
    ("BHP.AX", "BHP Group", "Australian Securities Exchange", "Action"),
    ("CBA.AX", "Commonwealth Bank", "Australian Securities Exchange", "Action"),
    ("CSL.AX", "CSL Limited", "Australian Securities Exchange", "Action"),
    ("NAB.AX", "National Australia Bank", "Australian Securities Exchange", "Action"),
    ("WBC.AX", "Westpac Banking", "Australian Securities Exchange", "Action"),
    ("ANZ.AX", "ANZ Group", "Australian Securities Exchange", "Action"),
    ("MQG.AX", "Macquarie Group", "Australian Securities Exchange", "Action"),
    ("WES.AX", "Wesfarmers", "Australian Securities Exchange", "Action"),
    ("TLS.AX", "Telstra", "Australian Securities Exchange", "Action"),
    ("WOW.AX", "Woolworths Group", "Australian Securities Exchange", "Action"),
    ("RIO.AX", "Rio Tinto", "Australian Securities Exchange", "Action"),
    ("FMG.AX", "Fortescue Metals Group", "Australian Securities Exchange", "Action"),
    ("ALL.AX", "Aristocrat Leisure", "Australian Securities Exchange", "Action"),
    ("GMG.AX", "Goodman Group", "Australian Securities Exchange", "Action"),
    ("TCL.AX", "Transurban Group", "Australian Securities Exchange", "Action"),

    # ═══ CANADA (TSX .TO) ────────────────────────────────────────────
    ("RY.TO", "Royal Bank of Canada", "Toronto Stock Exchange", "Action"),
    ("TD.TO", "Toronto-Dominion Bank", "Toronto Stock Exchange", "Action"),
    ("ENB.TO", "Enbridge", "Toronto Stock Exchange", "Action"),
    ("CNR.TO", "Canadian National Railway", "Toronto Stock Exchange", "Action"),
    ("BNS.TO", "Bank of Nova Scotia", "Toronto Stock Exchange", "Action"),
    ("SU.TO", "Suncor Energy", "Toronto Stock Exchange", "Action"),
    ("CNQ.TO", "Canadian Natural Resources", "Toronto Stock Exchange", "Action"),
    ("BMO.TO", "Bank of Montreal", "Toronto Stock Exchange", "Action"),
    ("CP.TO", "Canadian Pacific Kansas City", "Toronto Stock Exchange", "Action"),
    ("SHOP.TO", "Shopify", "Toronto Stock Exchange", "Action"),
    ("CSU.TO", "Constellation Software", "Toronto Stock Exchange", "Action"),
    ("L.TO", "Loblaw Companies", "Toronto Stock Exchange", "Action"),
    ("AEM.TO", "Agnico Eagle Mines", "Toronto Stock Exchange", "Action"),
    ("TRP.TO", "TC Energy", "Toronto Stock Exchange", "Action"),
    ("ATD.TO", "Alimentation Couche-Tard", "Toronto Stock Exchange", "Action"),

    # ═══ MEXIQUE (BMV .MX) ──────────────────────────────────────────
    ("AMXL.MX", "America Movil", "Bolsa Mexicana de Valores", "Action"),
    ("WALMEX.MX", "Walmart de Mexico", "Bolsa Mexicana de Valores", "Action"),
    ("FEMSAUBD.MX", "Fomento Economico Mexicano (FEMSA)", "Bolsa Mexicana de Valores", "Action"),
    ("GMEXICOB.MX", "Grupo Mexico", "Bolsa Mexicana de Valores", "Action"),
    ("BIMBOA.MX", "Grupo Bimbo", "Bolsa Mexicana de Valores", "Action"),
    ("GFNORTEO.MX", "Banorte", "Bolsa Mexicana de Valores", "Action"),
    ("CEMEXCPO.MX", "Cemex", "Bolsa Mexicana de Valores", "Action"),
    ("ASURB.MX", "Grupo Aeroportuario del Sureste", "Bolsa Mexicana de Valores", "Action"),

    # ═══ SINGAPOUR (SGX .SI) ────────────────────────────────────────
    ("D05.SI", "DBS Group", "Singapore Exchange", "Action"),
    ("O39.SI", "OCBC Bank", "Singapore Exchange", "Action"),
    ("U11.SI", "United Overseas Bank", "Singapore Exchange", "Action"),
    ("Z74.SI", "Singapore Telecommunications", "Singapore Exchange", "Action"),
    ("C52.SI", "ComfortDelGro", "Singapore Exchange", "Action"),
    ("C6L.SI", "Singapore Airlines", "Singapore Exchange", "Action"),
    ("S68.SI", "Singapore Exchange", "Singapore Exchange", "Action"),
    ("BN4.SI", "Keppel Ltd", "Singapore Exchange", "Action"),

    # ═══ AFRIQUE DU SUD (JSE .JO) ─────────────────────────────────
    ("NPN.JO", "Naspers", "Johannesburg Stock Exchange", "Action"),
    ("AGL.JO", "Anglo American", "Johannesburg Stock Exchange", "Action"),
    ("MTN.JO", "MTN Group", "Johannesburg Stock Exchange", "Action"),
    ("SBK.JO", "Standard Bank Group", "Johannesburg Stock Exchange", "Action"),
    ("FSR.JO", "FirstRand", "Johannesburg Stock Exchange", "Action"),
    ("BHG.JO", "BHP Group (JSE)", "Johannesburg Stock Exchange", "Action"),
    ("SHP.JO", "Shoprite Holdings", "Johannesburg Stock Exchange", "Action"),
    ("SOL.JO", "Sasol", "Johannesburg Stock Exchange", "Action"),
    ("SLM.JO", "Sanlam", "Johannesburg Stock Exchange", "Action"),
    ("ANG.JO", "Anglogold Ashanti", "Johannesburg Stock Exchange", "Action"),

    # Pakistan (Pakistan Stock Exchange), 'KAR' is Karachi — may not exist.
    # Arabie Saoudite (Tadawul .SR) ─────────────────────────────────
    ("2222.SR", "Saudi Aramco", "Saudi Stock Exchange (Tadawul)", "Action"),
    ("1120.SR", "Al Rajhi Bank", "Saudi Stock Exchange (Tadawul)", "Action"),
    ("7010.SR", "Saudi Telecom (STC)", "Saudi Stock Exchange (Tadawul)", "Action"),
    ("1010.SR", "Riyad Bank", "Saudi Stock Exchange (Tadawul)", "Action"),
    ("2010.SR", "SABIC", "Saudi Stock Exchange (Tadawul)", "Action"),

    # ═══ INDONÉSIE (IDX .JK) ───────────────────────────────────────
    ("BBCA.JK", "Bank Central Asia", "Indonesia Stock Exchange", "Action"),
    ("BBRI.JK", "Bank Rakyat Indonesia", "Indonesia Stock Exchange", "Action"),
    ("TLKM.JK", "Telkom Indonesia", "Indonesia Stock Exchange", "Action"),
    ("BMRI.JK", "Bank Mandiri", "Indonesia Stock Exchange", "Action"),
    ("ASII.JK", "Astra International", "Indonesia Stock Exchange", "Action"),

    # ═══ THAÏLANDE (SET .BK) ──────────────────────────────────────
    ("PTT.BK", "PTT PCL", "Stock Exchange of Thailand", "Action"),
    ("SCB.BK", "SCB X PCL", "Stock Exchange of Thailand", "Action"),
    ("AOT.BK", "Airports of Thailand", "Stock Exchange of Thailand", "Action"),
    ("CPALL.BK", "CP ALL PCL", "Stock Exchange of Thailand", "Action"),
    ("KBANK.BK", "Kasikornbank", "Stock Exchange of Thailand", "Action"),

    # ═══ TURQUIE (Borsa Istanbul .IS) ─────────────────────────────
    ("GARAN.IS", "Garanti BBVA", "Borsa Istanbul", "Action"),
    ("AKBNK.IS", "Akbank", "Borsa Istanbul", "Action"),
    ("ISCTR.IS", "Is Bankasi", "Borsa Istanbul", "Action"),
    ("THYAO.IS", "Turkish Airlines", "Borsa Istanbul", "Action"),
    ("KCHOL.IS", "Koc Holding", "Borsa Istanbul", "Action"),
    ("BIMAS.IS", "BIM Birlesik Magazalar", "Borsa Istanbul", "Action"),
    ("TUPRS.IS", "Tupras", "Borsa Istanbul", "Action"),
    ("SASA.IS", "Sasa Polyester", "Borsa Istanbul", "Action"),

    # ═══ CHILI (Santiago .SN) ──────────────────────────────────────
    ("SQM-B.SN", "SQM (Sociedad Quimica y Minera)", "Bolsa de Comercio de Santiago", "Action"),
    ("FALABELLA.SN", "Falabella", "Bolsa de Comercio de Santiago", "Action"),
    ("CENCOSUD.SN", "Cencosud", "Bolsa de Comercio de Santiago", "Action"),
    ("COPEC.SN", "Copec", "Bolsa de Comercio de Santiago", "Action"),
    ("BCI.SN", "Banco de Credito e Inversiones", "Bolsa de Comercio de Santiago", "Action"),

    # ═══ ARGENTINE (Buenos Aires .BA) ──────────────────────────────
    ("YPFD.BA", "YPF", "Buenos Aires Stock Exchange", "Action"),
    ("GGAL.BA", "Grupo Financiero Galicia", "Buenos Aires Stock Exchange", "Action"),
    ("PAMP.BA", "Pampa Energia", "Buenos Aires Stock Exchange", "Action"),
    ("TECO2.BA", "Telecom Argentina", "Buenos Aires Stock Exchange", "Action"),
    ("BMA.BA", "Banco Macro", "Buenos Aires Stock Exchange", "Action"),

    # ═══ RUSSIE (Moscow .ME) ─────────────────────────────────────
    # Note: post-2022 sanctions limit Yahoo Finance access.
    ("LKOH.ME", "Lukoil", "Moscow Exchange", "Action"),
    ("SBER.ME", "Sberbank", "Moscow Exchange", "Action"),
    ("ROSN.ME", "Rosneft", "Moscow Exchange", "Action"),
    ("NVTK.ME", "Novatek", "Moscow Exchange", "Action"),
    ("GMKN.ME", "Norilsk Nickel", "Moscow Exchange", "Action"),

    # ═══ MALAISIE (Bursa .KL) ─────────────────────────────────────
    ("1155.KL", "Malayan Banking (Maybank)", "Bursa Malaysia", "Action"),
    ("1295.KL", "Public Bank", "Bursa Malaysia", "Action"),
    ("1023.KL", "CIMB Group", "Bursa Malaysia", "Action"),
    ("5183.KL", "Petronas Chemicals", "Bursa Malaysia", "Action"),
    ("5225.KL", "IHH Healthcare", "Bursa Malaysia", "Action"),

    # ═══ PHILIPPINES (PSE .PS) ────────────────────────────────────
    ("SM.PS", "SM Investments", "Philippine Stock Exchange", "Action"),
    ("BDO.PS", "BDO Unibank", "Philippine Stock Exchange", "Action"),
    ("BPI.PS", "Bank of the Philippine Islands", "Philippine Stock Exchange", "Action"),
    ("TEL.PS", "PLDT", "Philippine Stock Exchange", "Action"),
    ("ALI.PS", "Ayala Land", "Philippine Stock Exchange", "Action"),

    # ═══ QATAR ────────────────────────────────────────────────────
    ("QNBK.QA", "Qatar National Bank", "Qatar Stock Exchange", "Action"),
    ("IQCD.QA", "Industries Qatar", "Qatar Stock Exchange", "Action"),
    ("QIBK.QA", "Qatar Islamic Bank", "Qatar Stock Exchange", "Action"),

    # ═══ UAE (Dubai .DU) ──────────────────────────────────────────
    ("EMIRATESNBD.DU", "Emirates NBD", "Dubai Financial Market", "Action"),
    ("EMAAR.DU", "Emaar Properties", "Dubai Financial Market", "Action"),
    ("DU.DU", "Du (Emirates Integrated Telecom)", "Dubai Financial Market", "Action"),

    # ═══ COLOMBIE ─────────────────────────────────────────────────
    ("ECOPETROL.CL", "Ecopetrol", "Bolsa de Valores de Colombia", "Action"),
    ("PFBCOLOM.CL", "Bancolombia Pref", "Bolsa de Valores de Colombia", "Action"),
    ("GRUPOSURA.CL", "Grupo Sura", "Bolsa de Valores de Colombia", "Action"),

    # ═══ POLOGNE (Warsaw) ────────────────────────────────────────
    ("PKO.WA", "PKO Bank Polski", "Warsaw Stock Exchange", "Action"),
    ("PKN.WA", "Orlen", "Warsaw Stock Exchange", "Action"),
    ("PZU.WA", "PZU", "Warsaw Stock Exchange", "Action"),
    ("DNP.WA", "Dino Polska", "Warsaw Stock Exchange", "Action"),
    ("KGH.WA", "KGHM Polska Miedz", "Warsaw Stock Exchange", "Action"),

    # ═══ AUTRICHE (Vienna) ──────────────────────────────────────────
    ("EBS.VI", "Erste Group Bank", "Vienna Stock Exchange", "Action"),
    ("OMV.VI", "OMV", "Vienna Stock Exchange", "Action"),
    ("VIG.VI", "Vienna Insurance Group", "Vienna Stock Exchange", "Action"),
    ("RBI.VI", "Raiffeisen Bank International", "Vienna Stock Exchange", "Action"),
    ("VOE.VI", "Voestalpine", "Vienna Stock Exchange", "Action"),

    # ═══ GRÈCE (Athens) ────────────────────────────────────────
    ("HTO.AT", "Hellenic Telecom (OTE)", "Athens Stock Exchange", "Action"),
    ("OPAP.AT", "OPAP", "Athens Stock Exchange", "Action"),
    ("MYTIL.AT", "Mytilineos", "Athens Stock Exchange", "Action"),
    ("EUROB.AT", "Eurobank Ergasias", "Athens Stock Exchange", "Action"),
    ("ALPHA.AT", "Alpha Bank", "Athens Stock Exchange", "Action"),
]


def main():
    if not TICKERS_CSV.exists():
        print(f"Fichier introuvable: {TICKERS_CSV}")
        sys.exit(1)

    existing = set()
    with open(TICKERS_CSV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ticker = line.split(";")[0].strip().upper()
            existing.add(ticker)

    added = 0
    skipped = 0
    with open(TICKERS_CSV, "a", encoding="utf-8") as f:
        for ticker, name, market, typ in NEW_TICKERS:
            if ticker.upper() in existing:
                skipped += 1
                continue
            f.write(f"{ticker};{name};{market};{typ}\n")
            existing.add(ticker.upper())
            added += 1

    print(f"Ajoutés: {added}, Déjà présents: {skipped}, Total final: {len(existing)}")


if __name__ == "__main__":
    main()
