"""Outils internes de l'agent Robot.

- Outils de LECTURE (#154, #162) : exécutés automatiquement, accès en lecture
  aux modules (finance, budget, santé, habitudes, agenda, livres + recherche
  dans les notes).
- Outils de MUTATION (#156, #164) : créent/modifient des données → exigent une
  confirmation explicite de l'utilisateur (cf. guardrails).

Chaque handler reçoit `(session, args)` et renvoie une chaîne lisible par le
modèle. Les requêtes vont directement aux modèles (robuste, sans dépendre de la
signature exacte des services).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, select


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[Session, dict], str]
    mutation: bool = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _month_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    start = today.replace(day=1)
    nxt = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return start, nxt


# ── Outils de lecture ────────────────────────────────────────────────────────

def _get_budget_month(session: Session, args: dict) -> str:
    from app.models.budget import BudgetTransaction
    today = dt.date.today()
    start, nxt = _month_bounds(today)
    rows = session.exec(
        select(BudgetTransaction).where(
            BudgetTransaction.date >= start, BudgetTransaction.date < nxt
        )
    ).all()
    revenus = sum(t.montant for t in rows if t.montant > 0)
    depenses = sum(-t.montant for t in rows if t.montant < 0)
    solde = revenus - depenses
    return (
        f"Budget {today:%B %Y} : revenus {revenus:.2f}, dépenses {depenses:.2f}, "
        f"solde {solde:.2f} ({len(rows)} transactions)."
    )


def _get_finance_portfolio(session: Session, args: dict) -> str:
    from app.models.finance import Position, SnapshotPortefeuille
    snap = session.exec(
        select(SnapshotPortefeuille).order_by(SnapshotPortefeuille.date.desc())
    ).first()
    n_pos = len(session.exec(select(Position)).all())
    if not snap:
        return f"Portefeuille : {n_pos} positions, aucun snapshot de valeur."
    plus_value = snap.valeur - (snap.investit or 0)
    return (
        f"Portefeuille au {snap.date} : valeur {snap.valeur:.2f}, investi "
        f"{snap.investit:.2f}, +/- value {plus_value:+.2f} ({n_pos} positions)."
    )


def _get_habitudes_today(session: Session, args: dict) -> str:
    from app.services.habitudes.entries import get_today_checklist
    rows = get_today_checklist(session)
    if not rows:
        return "Aucune habitude configurée."
    done = [r["habit"].nom for r in rows if r.get("entry")]
    todo = [r["habit"].nom for r in rows if not r.get("entry")]
    return (
        f"Habitudes du jour : {len(done)}/{len(rows)} faites. "
        f"Faites : {', '.join(done) or '—'}. Reste : {', '.join(todo) or '—'}."
    )


def _get_agenda_today(session: Session, args: dict) -> str:
    from app.models.agenda import Evenement, Tache
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time.min)
    end = dt.datetime.combine(today, dt.time.max)
    evs = session.exec(
        select(Evenement).where(Evenement.debut >= start, Evenement.debut <= end)
        .order_by(Evenement.debut)
    ).all()
    taches = session.exec(
        select(Tache).where(Tache.statut != "done").order_by(Tache.priorite)
    ).all()
    ev_txt = "; ".join(f"{e.debut:%H:%M} {e.titre}" for e in evs) or "aucun"
    t_txt = "; ".join(t.titre for t in taches[:5]) or "aucune"
    return f"Agenda du jour — événements : {ev_txt}. Tâches en cours : {t_txt}."


def _get_livres_stats(session: Session, args: dict) -> str:
    from app.models.livres import Book
    books = session.exec(select(Book)).all()
    by_statut: dict[str, int] = {}
    for b in books:
        by_statut[b.statut] = by_statut.get(b.statut, 0) + 1
    en_cours = [b.titre for b in books if b.statut == "en_cours"]
    parts = ", ".join(f"{k}: {v}" for k, v in by_statut.items()) or "aucun livre"
    return f"Livres ({parts}). En cours : {', '.join(en_cours) or '—'}."


def _search_notes(session: Session, args: dict) -> str:
    """RAG-lite (#162) : recherche dans notes/citations de livres + sessions d'étude."""
    q = str(args.get("query", "")).strip().lower()
    if not q:
        return "Requête vide."
    from app.models.etudes import SessionEtude
    from app.models.livres import BookNote, BookQuote
    hits: list[str] = []
    for n in session.exec(select(BookNote)).all():
        if q in (n.contenu or "").lower():
            hits.append(f"[note livre] {n.contenu[:200]}")
    for qt in session.exec(select(BookQuote)).all():
        if q in (qt.texte or "").lower():
            hits.append(f"[citation] {qt.texte[:200]}")
    for s in session.exec(select(SessionEtude)).all():
        blob = f"{s.sujet or ''} {s.note or ''}"
        if q in blob.lower():
            hits.append(f"[étude {s.date}] {blob[:200]}")
    if not hits:
        return f"Aucune note ne contient « {q} »."
    return "Résultats :\n- " + "\n- ".join(hits[:8])


# ── Outil de mutation (confirmation requise) ─────────────────────────────────

def _add_budget_transaction(session: Session, args: dict) -> str:
    """Crée une dépense/un revenu (#156, #164 « ajoute 40$ d'épicerie hier »)."""
    from app.models.budget import BudgetTransaction
    montant = float(args.get("montant"))
    marchand = str(args.get("marchand", "") or "")
    description = str(args.get("description", "") or "")
    date_str = args.get("date")
    date = dt.date.fromisoformat(date_str) if date_str else dt.date.today()
    tx = BudgetTransaction(
        date=date, montant=montant, marchand=marchand,
        description=description, auto=True,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    signe = "revenu" if montant > 0 else "dépense"
    return f"{signe.capitalize()} créée : {abs(montant):.2f} « {marchand or description} » le {date}."


TOOLS: dict[str, Tool] = {
    "get_budget_month": Tool(
        "get_budget_month",
        "Résumé du budget du mois en cours (revenus, dépenses, solde).",
        {"type": "object", "properties": {}},
        _get_budget_month,
    ),
    "get_finance_portfolio": Tool(
        "get_finance_portfolio",
        "État du portefeuille d'investissement (valeur, investi, plus-value).",
        {"type": "object", "properties": {}},
        _get_finance_portfolio,
    ),
    "get_habitudes_today": Tool(
        "get_habitudes_today",
        "Habitudes du jour : combien faites / restantes.",
        {"type": "object", "properties": {}},
        _get_habitudes_today,
    ),
    "get_agenda_today": Tool(
        "get_agenda_today",
        "Événements du jour et tâches en cours.",
        {"type": "object", "properties": {}},
        _get_agenda_today,
    ),
    "get_livres_stats": Tool(
        "get_livres_stats",
        "Statistiques de lecture (livres par statut, en cours).",
        {"type": "object", "properties": {}},
        _get_livres_stats,
    ),
    "search_notes": Tool(
        "search_notes",
        "Recherche un mot/sujet dans les notes & citations de livres et les sessions d'étude.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Terme à chercher"}},
            "required": ["query"],
        },
        _search_notes,
    ),
    "add_budget_transaction": Tool(
        "add_budget_transaction",
        "Ajoute une transaction au budget (dépense si montant négatif, revenu si positif). "
        "Action sensible : nécessite la confirmation de l'utilisateur.",
        {
            "type": "object",
            "properties": {
                "montant": {"type": "number", "description": "Montant ; négatif = dépense, positif = revenu"},
                "marchand": {"type": "string"},
                "description": {"type": "string"},
                "date": {"type": "string", "description": "Date ISO AAAA-MM-JJ (défaut aujourd'hui)"},
            },
            "required": ["montant"],
        },
        _add_budget_transaction,
        mutation=True,
    ),
}


def tool_definitions() -> list[dict]:
    """Définitions d'outils au format API Claude."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


def is_mutation(name: str) -> bool:
    t = TOOLS.get(name)
    return bool(t and t.mutation)


def dispatch(session: Session, name: str, args: dict) -> str:
    """Exécute un outil et renvoie son résultat texte (ou un message d'erreur)."""
    tool = TOOLS.get(name)
    if not tool:
        return f"Outil inconnu : {name}"
    try:
        return tool.handler(session, args or {})
    except Exception as e:  # robuste : jamais de crash de l'agent sur un outil
        return f"Erreur outil {name} : {e}"


def parse_args(raw) -> dict:
    """Normalise des arguments (dict ou JSON string) en dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
