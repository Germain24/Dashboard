"""Tests TDD — parseur de relevés Mastercard Desjardins (PDF, #256)."""

from __future__ import annotations

import datetime as dt

from app.services.budget.desjardins_pdf import (
    _unwrap_pdf,
    parse_desjardins_eop,
    parse_desjardins_mastercard,
)

# Relevé compte chèque (EOP), extrait pypdf mode layout (dernier nombre = solde).
_EOP_TEXT = """     du 1er octobre  au 31 octobre 2025   Page 1 de 1
EOP                           COMPTE PROFIT JEUNESSE DESJARDINS
  DateCode  Description  FraisRetrait Depot Solde
                Solde reporte                                                       1 718.32
   2 OCTACH     Achat / ALFID SERVICES                              655.00       1 063.32
   8 OCTRA      Assurance / DESJARDINS ASS. GENERALES                38.63       1 024.69
   9 OCTDDI     Paie / Le Petit Dep                                              47.43      1 072.12
   9 OCTVMW     Virement Interac de / Germain De Sou/                          5 998.02      7 070.14
   9 OCTPWW     Paiement facture - AccesD Internet / Trimestre      1 888.40       5 181.74
  23 OCTDDI     Paie / Le Petit Dep                                            581.34      5 763.08
  31 OCTINT     Interet sur EOP                                                  0.35      5 763.43
                                COMPTE D'EPARGNE ET DE PLACEMENT
ET 1Compte d'epargne
                Solde reporte                                                       0.00
"""

# Reproduit la sortie de pypdf : transactions concaténées, date JJMMJJMM sans
# espace, accents en mojibake, paiements en « CR » sans remise.
_TEXT = (
    "DATE DU RELEV�09012026\n"
    "5598 22** **** 800430012026       95,64     10,00\n"  # en-tête : date d'échéance JJMMAAAA → ignorée
    "24122412PATISSERIE NOTRE MAISO   MONTREAL     QC 2,00 %       15,40"
    "30123012PAIEMENT CAISSE         28,19CR"  # paiement → exclu (pas de remise)
    "01010201UBER CANADA/UBEREATS     TORONTO      ON 2,00 %       30,74"
    "07010701COSTCO WHOLESALE W527    MONTREAL     QC 0,50 %      243,36"
)


def test_parses_purchases_with_inferred_year():
    txns = parse_desjardins_mastercard(_TEXT)
    assert txns == [
        (dt.date(2025, 12, 24), -15.40, "PATISSERIE NOTRE MAISO MONTREAL QC"),
        (dt.date(2026, 1, 1), -30.74, "UBER CANADA/UBEREATS TORONTO ON"),
        (dt.date(2026, 1, 7), -243.36, "COSTCO WHOLESALE W527 MONTREAL QC"),
    ]


def test_excludes_payments():
    txns = parse_desjardins_mastercard(_TEXT)
    assert all("PAIEMENT CAISSE" not in m for _, _, m in txns)


def test_ignores_statement_header_dates():
    # La date d'échéance 30012026 (mois « 26 » invalide) ne doit pas créer de ligne.
    txns = parse_desjardins_mastercard(_TEXT)
    assert all(montant < 0 for _, montant, _ in txns)
    assert len(txns) == 3


def test_amounts_sum_matches_statement_total():
    # Le relevé annonce « Achats / débits + 771,55 » ; ici le sous-ensemble = 289,50.
    txns = parse_desjardins_mastercard(_TEXT)
    assert round(sum(-m for _, m, _ in txns), 2) == 289.50


def test_empty_without_statement_date():
    assert parse_desjardins_mastercard("aucune date de relevé ici") == []


# ─── Compte chèque (EOP) ─────────────────────────────────────────────────────

def test_eop_signs_via_solde_delta():
    out = parse_desjardins_eop(_EOP_TEXT)
    assert (dt.date(2025, 10, 2), -655.00, "Achat / ALFID SERVICES") in out
    assert (dt.date(2025, 10, 9), 47.43, "Paie / Le Petit Dep") in out          # dépôt > 0
    assert (dt.date(2025, 10, 9), 5998.02, "Virement Interac de / Germain De Sou/") in out
    assert (dt.date(2025, 10, 9), -1888.40, "Paiement facture - AccesD Internet / Trimestre") in out
    assert (dt.date(2025, 10, 31), 0.35, "Interet sur EOP") in out


def test_eop_stops_at_savings_section():
    out = parse_desjardins_eop(_EOP_TEXT)
    # 7 opérations sur le compte chèque, rien de la section épargne.
    assert len(out) == 7


def test_eop_excludes_internal_transfers():
    text = (
        "au 31 mai 2026\nEOP\n"
        "                Solde reporte                       100.00\n"
        "   5 MAIVIR     Virement - AccesD Internet / a ET           60.00       40.00\n"
        "  10 MAIDDI     Paie / Le Petit Dep                                  500.00      540.00\n"
    )
    out = parse_desjardins_eop(text)
    # Le virement interne (vers épargne ET) est exclu ; la paie reste.
    assert [d[2] for d in out] == ["Paie / Le Petit Dep"]
    assert out[0][1] == 500.0


def test_eop_excludes_mastercard_payments():
    # Les paiements de la carte (Remises Mastercard) sont exclus (double comptage
    # avec les achats du relevé carte). Le solde évolue quand même correctement.
    text = (
        "au 31 janvier 2026\nEOP\n"
        "                Solde reporte                       1000.00\n"
        "   5 JANPWW     Paiement facture - AccesD Internet / Remises Mastercard   40.00       960.00\n"
        "  15 JANDDI     Paie / Le Petit Dep                                      500.00      1460.00\n"
    )
    out = parse_desjardins_eop(text)
    assert [d[2] for d in out] == ["Paie / Le Petit Dep"]
    assert out[0][1] == 500.0   # 1460 - 960, solde après le paiement carte exclu


def test_unwrap_passthrough_real_pdf():
    assert _unwrap_pdf(b"%PDF-1.3\nstuff\n%%EOF") == b"%PDF-1.3\nstuff\n%%EOF"
    assert _unwrap_pdf(b"\xac\xed\x00\x05junk%PDF-1.3 body %%EOFtrailer")[:5] == b"%PDF-"
    assert _unwrap_pdf(b"not a pdf at all") is None
