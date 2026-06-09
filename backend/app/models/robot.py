"""Modèles Robot / IA — chat agent Claude (CONV N).

Trois tables :
  - RobotConversation : un fil de discussion (titre, modèle, cumul tokens/coût).
  - RobotMessage      : un message du fil (role user/assistant, contenu).
  - RobotAction       : journal des actions (tool use) — audit + garde-fous (#163).
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Field, SQLModel


class RobotConversation(SQLModel, table=True):
    __tablename__ = "robot_conversation"

    id: int | None = Field(default=None, primary_key=True)
    titre: str = "Nouvelle conversation"
    model: str = ""
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    # Cumul d'usage (#165)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0


class RobotMessage(SQLModel, table=True):
    __tablename__ = "robot_message"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="robot_conversation.id", index=True)
    role: str  # "user" | "assistant"
    content: str = ""
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class RobotAction(SQLModel, table=True):
    __tablename__ = "robot_action"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int | None = Field(
        default=None, foreign_key="robot_conversation.id", index=True
    )
    tool: str                       # nom de l'outil appelé
    args: str = "{}"                # arguments JSON
    # pending : attend confirmation (action sensible #156/#163)
    # executed : exécutée ; denied : refusée ; auto : lecture seule auto-exécutée
    statut: str = "auto"
    result: str = ""
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
