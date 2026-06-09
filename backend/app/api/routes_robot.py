"""Router module Robot / IA — chat agent Claude (CONV N).

Endpoints :
  - GET  /ping, /status                  état du module / clé API
  - GET/POST /settings                   réglages modèle/effort/max_tokens (#161)
  - POST /conversations, GET, GET/{id}, DELETE/{id}   persistance (#158)
  - POST /chat                           chat streaming SSE (#153/#154/#157)
  - POST /actions/{id}/confirm|deny      mutations sur confirmation (#156/#163)
  - GET  /recap                          récapitulatif quotidien (#159)
  - GET  /insights                       insights proactifs (#160)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.robot import agent as agent_svc
from app.services.robot import conversations as conv_svc
from app.services.robot import insights as insights_svc
from app.services.robot import preferences as prefs_svc
from app.services.robot import recap as recap_svc
from app.services.robot.tools import tool_definitions

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"module": "robot", "ready": agent_svc.has_api_key()}


@router.get("/status")
def status() -> dict:
    prefs = prefs_svc.get_prefs()
    return {
        "api_key_configured": agent_svc.has_api_key(),
        "model": prefs["model"],
        "effort": prefs["effort"],
        "max_tokens": prefs["max_tokens"],
        "tools": [t["name"] for t in tool_definitions()],
    }


# ── Réglages (#161) ──────────────────────────────────────────────────────────

class PrefsUpdate(BaseModel):
    model: str | None = None
    effort: str | None = None
    max_tokens: int | None = None


@router.get("/settings")
def get_settings() -> dict:
    return prefs_svc.get_prefs()


@router.post("/settings")
def update_settings(body: PrefsUpdate) -> dict:
    try:
        return prefs_svc.set_prefs(body.model, body.effort, body.max_tokens)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Conversations (#158) ─────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    titre: str = ""


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationCreate, session: Session = Depends(get_session)):
    return conv_svc.create_conversation(session, body.titre, prefs_svc.get_prefs()["model"])


@router.get("/conversations")
def list_conversations(session: Session = Depends(get_session)):
    return conv_svc.list_conversations(session)


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = conv_svc.get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(404)
    return {"conversation": conv, "messages": conv_svc.get_messages(session, conv_id)}


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = conv_svc.get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(404)
    for m in conv_svc.get_messages(session, conv_id):
        session.delete(m)
    session.delete(conv)
    session.commit()


# ── Chat streaming (#153/#157) ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: int
    message: str


@router.post("/chat")
def chat(body: ChatRequest, session: Session = Depends(get_session)):
    conv = conv_svc.get_conversation(session, body.conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation introuvable.")
    gen = agent_svc.stream_chat(session, body.conversation_id, body.message)
    return StreamingResponse(
        gen, media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Actions / mutations (#156/#163) ──────────────────────────────────────────

@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: int, session: Session = Depends(get_session)):
    res = agent_svc.confirm_action(session, action_id)
    if not res.get("ok"):
        raise HTTPException(400, res.get("message", "Échec"))
    return res


@router.post("/actions/{action_id}/deny")
def deny_action(action_id: int, session: Session = Depends(get_session)):
    res = agent_svc.deny_action(session, action_id)
    if not res.get("ok"):
        raise HTTPException(400, res.get("message", "Échec"))
    return res


# ── Recap & insights (#159/#160) ─────────────────────────────────────────────

@router.get("/recap")
def recap(session: Session = Depends(get_session)):
    return recap_svc.daily_recap(session)


@router.get("/insights")
def insights(session: Session = Depends(get_session)):
    return insights_svc.get_insights(session)
