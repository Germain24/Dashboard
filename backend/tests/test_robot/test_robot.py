"""Tests module Robot (CONV N) — logique pure & DB (sans appel API réel)."""

import datetime as dt

from sqlmodel import Session, SQLModel, create_engine

from app.models.budget import BudgetTransaction  # noqa: F401
from app.models.robot import RobotConversation  # noqa: F401
from app.services.robot import conversations as conv_svc
from app.services.robot import tools as tools_svc
from app.services.robot.guardrails import action_status, requires_confirmation
from app.services.robot.insights import build_insights
from app.services.robot.pricing import compute_cost, model_pricing


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


# ── Pricing (#165) ───────────────────────────────────────────────────────────

def test_pricing_known_model():
    assert model_pricing("claude-opus-4-8") == (5.0, 25.0)


def test_pricing_unknown_defaults_to_opus():
    assert model_pricing("inconnu") == (5.0, 25.0)


def test_compute_cost_basic():
    # 1M input + 1M output Opus = 5 + 25 = 30
    assert compute_cost("claude-opus-4-8", 1_000_000, 1_000_000) == 30.0


def test_compute_cost_cache_cheaper():
    full = compute_cost("claude-opus-4-8", 1_000_000, 0)
    cached = compute_cost("claude-opus-4-8", 0, 0, cache_read_tokens=1_000_000)
    assert cached < full
    assert cached == round(5.0 * 0.1, 6)


# ── Guardrails (#163) ────────────────────────────────────────────────────────

def test_read_tool_not_confirmed():
    assert requires_confirmation("get_budget_month") is False
    assert action_status("get_budget_month", confirmed=False) == "auto"


def test_mutation_tool_requires_confirmation():
    assert requires_confirmation("add_budget_transaction") is True
    assert action_status("add_budget_transaction", confirmed=False) == "pending"
    assert action_status("add_budget_transaction", confirmed=True) == "executed"


# ── Tools (#154/#156/#164) ───────────────────────────────────────────────────

def test_tool_definitions_shape():
    defs = tools_svc.tool_definitions()
    assert all({"name", "description", "input_schema"} <= set(d) for d in defs)
    names = {d["name"] for d in defs}
    assert "get_budget_month" in names and "add_budget_transaction" in names


def test_parse_args_variants():
    assert tools_svc.parse_args({"a": 1}) == {"a": 1}
    assert tools_svc.parse_args('{"a": 1}') == {"a": 1}
    assert tools_svc.parse_args("pas du json") == {}
    assert tools_svc.parse_args("") == {}


def test_dispatch_unknown_tool():
    assert "inconnu" in tools_svc.dispatch(_session(), "nope", {}).lower()


def test_add_budget_transaction_creates_row():
    s = _session()
    res = tools_svc.dispatch(s, "add_budget_transaction",
                             {"montant": -40, "marchand": "Épicerie", "date": "2026-06-07"})
    assert "épicerie" in res.lower() or "epicerie" in res.lower()
    rows = s.exec(__import__("sqlmodel").select(BudgetTransaction)).all()
    assert len(rows) == 1
    assert rows[0].montant == -40
    assert rows[0].date == dt.date(2026, 6, 7)


def test_get_budget_month_reads(monkeypatch):
    s = _session()
    today = dt.date.today()
    s.add(BudgetTransaction(date=today, montant=100.0, marchand="Salaire"))
    s.add(BudgetTransaction(date=today, montant=-30.0, marchand="Café"))
    s.commit()
    res = tools_svc.dispatch(s, "get_budget_month", {})
    assert "100" in res and "30" in res


# ── Conversations + usage (#158/#165) ────────────────────────────────────────

def test_conversation_lifecycle_and_usage():
    s = _session()
    conv = conv_svc.create_conversation(s, "", "claude-opus-4-8")
    conv_svc.add_message(s, conv.id, "user", "Bonjour, peux-tu m'aider avec mon budget ?")
    msgs = conv_svc.get_messages(s, conv.id)
    assert len(msgs) == 1
    # Titre auto depuis le 1er message
    assert s.get(RobotConversation, conv.id).titre.startswith("Bonjour")
    cost = conv_svc.accumulate_usage(s, conv.id, "claude-opus-4-8",
                                     {"input_tokens": 1000, "output_tokens": 500})
    assert cost > 0
    refreshed = s.get(RobotConversation, conv.id)
    assert refreshed.input_tokens == 1000
    assert refreshed.output_tokens == 500
    assert refreshed.cost_usd == cost


# ── Insights (#160) ──────────────────────────────────────────────────────────

def test_insights_low_habits():
    out = build_insights({"habits_done": 1, "habits_total": 5})
    assert any(i["level"] == "warning" for i in out)


def test_insights_all_habits_done():
    out = build_insights({"habits_done": 4, "habits_total": 4})
    assert any(i["level"] == "success" for i in out)


def test_insights_budget_overspend():
    out = build_insights({"budget_revenus": 100, "budget_depenses": 200})
    assert any(i["level"] == "alert" for i in out)


def test_insights_empty_when_nothing():
    assert build_insights({}) == []
