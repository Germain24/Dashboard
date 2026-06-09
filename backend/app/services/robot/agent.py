"""Agent Claude : chat streaming avec tool use, caching et garde-fous.

Implémente #153 (chat réel claude-opus-4-8), #154 (tool use lecture), #155
(prompt caching du système), #156/#163 (mutations sur confirmation), #157
(streaming SSE), #165 (cumul tokens/coût).

Le SDK `anthropic` n'est importé qu'à l'usage : le module reste importable même
sans la dépendance / sans clé API (dégradation propre).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from sqlmodel import Session

from app.core.config import settings
from app.models.robot import RobotAction
from app.services.robot import conversations as conv_svc
from app.services.robot.tools import TOOLS, dispatch, is_mutation, parse_args, tool_definitions

DEFAULT_SYSTEM = (
    "Tu es l'assistant personnel de Mission Control, un tableau de bord de vie "
    "(finance, budget, santé, entraînement, habitudes, agenda, études, cuisine, "
    "livres). Tu réponds en français, de façon concise et actionnable.\n\n"
    "Tu as des outils en LECTURE pour consulter les données réelles de "
    "l'utilisateur : utilise-les plutôt que de deviner. Pour toute action qui "
    "MODIFIE des données (ex. ajouter une dépense), l'outil correspondant est "
    "soumis à confirmation : décris ce que tu vas faire et demande validation, "
    "n'affirme jamais qu'une modification est faite tant qu'elle n'est pas confirmée."
)


def system_prompt() -> str:
    return settings.robot_system_prompt or DEFAULT_SYSTEM


def has_api_key() -> bool:
    return bool(settings.anthropic_api_key)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _build_messages(session: Session, conv_id: int) -> list[dict]:
    """Historique de la conversation au format API (texte simple)."""
    out: list[dict] = []
    for m in conv_svc.get_messages(session, conv_id):
        if m.role in ("user", "assistant") and m.content:
            out.append({"role": m.role, "content": m.content})
    return out


def stream_chat(session: Session, conv_id: int, user_message: str) -> Iterator[str]:
    """Génère des évènements SSE pour un tour de chat.

    Évènements : {"type":"token","text":...} | {"type":"pending_action",...}
    | {"type":"error","message":...} | {"type":"done","cost":...,"total_cost":...}
    """
    conv_svc.add_message(session, conv_id, "user", user_message)

    if not has_api_key():
        yield _sse({"type": "error", "message":
                    "Clé API Claude absente. Renseigne ANTHROPIC_API_KEY pour activer le chat."})
        yield _sse({"type": "done", "cost": 0.0, "total_cost": 0.0})
        return

    from app.services.robot.preferences import get_prefs
    prefs = get_prefs()
    model = prefs["model"]
    max_tokens = prefs["max_tokens"]
    effort = prefs["effort"]
    messages = _build_messages(session, conv_id)
    sys_blocks = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
    tools = tool_definitions()

    try:
        client = _client()
    except Exception as e:
        yield _sse({"type": "error", "message": f"SDK Claude indisponible : {e}"})
        yield _sse({"type": "done", "cost": 0.0, "total_cost": 0.0})
        return

    assistant_text_parts: list[str] = []
    turn_cost = 0.0
    pending = False

    for _ in range(6):  # garde-fou : 6 itérations d'outils max
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            system=sys_blocks,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
        )
        if effort:
            kwargs["output_config"] = {"effort": effort}

        try:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    assistant_text_parts.append(text)
                    yield _sse({"type": "token", "text": text})
                final = stream.get_final_message()
        except Exception as e:
            yield _sse({"type": "error", "message": f"Erreur API Claude : {e}"})
            break

        usage = getattr(final, "usage", None)
        if usage is not None:
            turn_cost += conv_svc.accumulate_usage(
                session, conv_id, model,
                {
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                },
            )

        if getattr(final, "stop_reason", None) != "tool_use":
            break

        # Rejoue le tour avec les résultats d'outils.
        messages.append({"role": "assistant", "content": [b.model_dump() for b in final.content]})
        tool_results = []
        for block in final.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            args = parse_args(block.input)
            if is_mutation(name):
                # Action sensible : on NE l'exécute PAS, on la met en attente (#156/#163).
                action = RobotAction(
                    conversation_id=conv_id, tool=name,
                    args=json.dumps(args, ensure_ascii=False), statut="pending",
                )
                session.add(action)
                session.commit()
                session.refresh(action)
                pending = True
                yield _sse({"type": "pending_action", "id": action.id, "tool": name, "args": args})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": (
                        f"EN ATTENTE DE CONFIRMATION (action #{action.id}). Décris à "
                        "l'utilisateur ce que tu vas faire et demande sa validation. "
                        "Ne considère pas l'action comme effectuée."
                    ),
                })
            else:
                result = dispatch(session, name, args)
                session.add(RobotAction(
                    conversation_id=conv_id, tool=name,
                    args=json.dumps(args, ensure_ascii=False), statut="auto", result=result[:2000],
                ))
                session.commit()
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": result,
                })
        messages.append({"role": "user", "content": tool_results})
        if pending:
            break  # on attend la confirmation utilisateur avant de continuer

    text = "".join(assistant_text_parts).strip()
    if text:
        conv_svc.add_message(session, conv_id, "assistant", text)
    conv = conv_svc.get_conversation(session, conv_id)
    yield _sse({"type": "done", "cost": round(turn_cost, 6),
                "total_cost": round(conv.cost_usd, 6) if conv else 0.0})


def confirm_action(session: Session, action_id: int) -> dict:
    """Exécute une action en attente (mutation confirmée par l'utilisateur, #156)."""
    action = session.get(RobotAction, action_id)
    if not action:
        return {"ok": False, "message": "Action introuvable."}
    if action.statut != "pending":
        return {"ok": False, "message": f"Action déjà {action.statut}."}
    if not is_mutation(action.tool):
        return {"ok": False, "message": "Action non confirmable."}
    result = dispatch(session, action.tool, parse_args(action.args))
    action.statut = "executed"
    action.result = result[:2000]
    session.add(action)
    session.commit()
    return {"ok": True, "result": result}


def deny_action(session: Session, action_id: int) -> dict:
    action = session.get(RobotAction, action_id)
    if not action or action.statut != "pending":
        return {"ok": False, "message": "Action introuvable ou déjà traitée."}
    action.statut = "denied"
    session.add(action)
    session.commit()
    return {"ok": True}


# Exposé pour les tests / le recap.
ALL_TOOL_NAMES = list(TOOLS.keys())
