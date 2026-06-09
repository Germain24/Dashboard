"""Persistance des conversations Robot (#158) + cumul d'usage (#165)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.robot import RobotConversation, RobotMessage
from app.services.robot.pricing import compute_cost


def create_conversation(session: Session, titre: str = "", model: str = "") -> RobotConversation:
    conv = RobotConversation(titre=titre or "Nouvelle conversation", model=model)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def list_conversations(session: Session) -> list[RobotConversation]:
    return list(session.exec(
        select(RobotConversation).order_by(RobotConversation.updated_at.desc())
    ).all())


def get_conversation(session: Session, conv_id: int) -> RobotConversation | None:
    return session.get(RobotConversation, conv_id)


def get_messages(session: Session, conv_id: int) -> list[RobotMessage]:
    return list(session.exec(
        select(RobotMessage).where(RobotMessage.conversation_id == conv_id)
        .order_by(RobotMessage.created_at, RobotMessage.id)
    ).all())


def add_message(session: Session, conv_id: int, role: str, content: str) -> RobotMessage:
    msg = RobotMessage(conversation_id=conv_id, role=role, content=content)
    session.add(msg)
    conv = session.get(RobotConversation, conv_id)
    if conv:
        conv.updated_at = dt.datetime.utcnow()
        # Titre auto depuis le 1er message utilisateur.
        if role == "user" and conv.titre == "Nouvelle conversation":
            conv.titre = (content[:60] + "…") if len(content) > 60 else content
        session.add(conv)
    session.commit()
    session.refresh(msg)
    return msg


def accumulate_usage(session: Session, conv_id: int, model: str, usage: dict) -> float:
    """Ajoute l'usage d'un appel au cumul de la conversation. Retourne le coût de l'appel."""
    inp = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    cr = int(usage.get("cache_read_input_tokens", 0) or 0)
    cc = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cost = compute_cost(model, inp, out, cr, cc)
    conv = session.get(RobotConversation, conv_id)
    if conv:
        conv.input_tokens += inp
        conv.output_tokens += out
        conv.cache_read_tokens += cr
        conv.cache_creation_tokens += cc
        conv.cost_usd = round(conv.cost_usd + cost, 6)
        session.add(conv)
        session.commit()
    return cost
