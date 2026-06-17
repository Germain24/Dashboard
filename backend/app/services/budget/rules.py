import re
from typing import Any

from sqlmodel import Session, select

from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction


def apply_rules_pure(description: str, rules: list[dict]) -> int | None:
    sorted_rules = sorted(rules, key=lambda r: r["priorite"], reverse=True)
    for rule in sorted_rules:
        if re.search(rule["pattern"], description, re.IGNORECASE):
            return rule["category_id"]
    return None


def get_all_rules(session: Session) -> list[dict]:
    rules = session.exec(select(BudgetRule)).all()
    return [{"pattern": r.pattern, "category_id": r.category_id, "priorite": r.priorite} for r in rules]


def apply_rules_to_transaction(session: Session, description: str) -> int | None:
    return apply_rules_pure(description, get_all_rules(session))


def reapply_all_rules(session: Session) -> int:
    rules = get_all_rules(session)
    transactions = session.exec(select(BudgetTransaction)).all()
    updated = 0
    for t in transactions:
        cat_id = apply_rules_pure(f"{t.marchand} {t.description}", rules)
        if cat_id and t.category_id != cat_id:
            t.category_id = cat_id
            session.add(t)
            updated += 1
    session.commit()
    return updated


# ─── Règles apprenables depuis l'historique catégorisé à la main (#258) ──────

def _learn_key(marchand: str) -> str | None:
    """Clé d'apprentissage = premier token alphabétique significatif (≥3 lettres).

    « METRO INC », « METRO #123 » et « METRO PLATEAU » partagent la clé METRO,
    qui devient un motif de règle réutilisable.
    """
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", (marchand or "").upper())
    return tokens[0] if tokens else None


def suggest_rules_from_history(
    transactions: list[Any], existing_rules: list[dict], *, min_occurrences: int = 3,
) -> list[dict]:
    """Propose des règles à partir des transactions catégorisées à la main.

    Une suggestion n'est émise que si, pour un même marchand (clé), toutes les
    transactions catégorisées pointent vers UNE seule catégorie (pureté), avec
    au moins `min_occurrences` exemples, et qu'aucune règle existante ne couvre
    déjà ce marchand. Pur et testable.
    """
    groups: dict[str, dict] = {}
    for t in transactions:
        if t.category_id is None:
            continue
        key = _learn_key(t.marchand)
        if not key:
            continue
        g = groups.setdefault(key, {"cats": {}, "total": 0})
        g["cats"][t.category_id] = g["cats"].get(t.category_id, 0) + 1
        g["total"] += 1

    out: list[dict] = []
    for key, g in groups.items():
        if g["total"] < min_occurrences or len(g["cats"]) != 1:
            continue
        if apply_rules_pure(key, existing_rules) is not None:
            continue  # déjà couvert par une règle existante
        out.append({"pattern": key, "category_id": next(iter(g["cats"])), "occurrences": g["total"]})
    out.sort(key=lambda r: (-r["occurrences"], r["pattern"]))
    return out


def learn_rules(session: Session, *, min_occurrences: int = 3, apply: bool = False) -> dict:
    """Calcule (et optionnellement crée) des règles apprises de l'historique.

    Avec `apply=True`, crée les `BudgetRule` suggérées puis réapplique toutes
    les règles (les transactions non catégorisées du même marchand sont
    rattrapées). Retourne les suggestions enrichies du nom de catégorie.
    """
    transactions = session.exec(select(BudgetTransaction)).all()
    existing = get_all_rules(session)
    suggestions = suggest_rules_from_history(transactions, existing, min_occurrences=min_occurrences)

    noms = {c.id: c.nom for c in session.exec(select(BudgetCategory)).all()}
    for s in suggestions:
        s["category_nom"] = noms.get(s["category_id"], "")

    created, updated = 0, 0
    if apply and suggestions:
        for s in suggestions:
            session.add(BudgetRule(pattern=s["pattern"], category_id=s["category_id"], priorite=0))
            created += 1
        session.commit()
        updated = reapply_all_rules(session)
    return {"suggestions": suggestions, "created": created, "recategorised": updated}
