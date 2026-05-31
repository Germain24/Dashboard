import re
from sqlmodel import Session, select
from app.models.budget import BudgetRule, BudgetTransaction


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
