"""
agents/responder_agent.py
Genera borradores de respuesta para interacciones que lo requieren.
Encola en pending_replies.json para aprobación de Abel.
"""
import json
import os
from datetime import datetime
from integrations.claude_client import draft_reply
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "./data"
PENDING_FILE = f"{DATA_DIR}/pending_replies.json"


def _load_pending() -> list:
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_pending(pending: list):
    with open(PENDING_FILE, "w") as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)


def run(interactions: list) -> list:
    """
    Genera drafts de respuesta para interacciones que requieren reply.
    No publica nada — solo encola para aprobación.
    """
    to_respond = [
        i for i in interactions
        if i.get("requiere_respuesta")
        and i.get("intencion") not in ("spam", "troll")
    ]

    print(f"\n[RESPONDER] {len(to_respond)} respuestas a redactar")
    pending = _load_pending()
    new_replies = []

    # IDs ya en cola para no duplicar
    existing_ids = {p.get("interaction_id") for p in pending}

    for interaction in to_respond:
        if interaction.get("interaction_id") in existing_ids:
            continue

        try:
            reply_data = draft_reply(
                mensaje_original=interaction.get("texto", ""),
                usuario=interaction.get("usuario", ""),
                canal=interaction.get("canal", ""),
                tipo=interaction.get("tipo", "comment"),
                intencion=interaction.get("intencion", ""),
                contexto_lead=interaction.get("profile")
            )

            reply_entry = {
                "reply_id": f"reply_{interaction['interaction_id']}_{datetime.now().strftime('%H%M%S')}",
                "interaction_id": interaction.get("interaction_id"),
                "canal": interaction.get("canal"),
                "tipo": interaction.get("tipo"),
                "post_id": interaction.get("post_id"),
                "comment_id": interaction.get("comment_id"),
                "conversation_id": interaction.get("conversation_id"),
                "message_id": interaction.get("message_id"),
                "usuario": interaction.get("usuario"),
                "mensaje_original": interaction.get("texto"),
                "draft": reply_data.get("draft", ""),
                "tono": reply_data.get("tono", ""),
                "incluye_cta": reply_data.get("incluye_cta", False),
                "chars": reply_data.get("chars", 0),
                "intencion": interaction.get("intencion"),
                "lead_id": interaction.get("lead_id", ""),
                "alerta": interaction.get("alerta", ""),
                "estado": "pending_approval",
                "created_at": datetime.now().isoformat()
            }

            pending.append(reply_entry)
            new_replies.append(reply_entry)

            print(
                f"[RESPONDER] Draft listo: {interaction['canal'].upper()} | "
                f"@{interaction.get('usuario')} | "
                f"{reply_data.get('chars', 0)} chars"
            )

        except Exception as e:
            print(f"[RESPONDER] Error drafteando para {interaction.get('interaction_id')}: {e}")

    _save_pending(pending)
    print(f"[RESPONDER] {len(new_replies)} drafts encolados para aprobación")
    return new_replies


def mark_approved(reply_id: str) -> dict:
    """Marca un reply como aprobado y retorna sus datos para publicar."""
    pending = _load_pending()
    for reply in pending:
        if reply.get("reply_id") == reply_id:
            reply["estado"] = "approved"
            reply["approved_at"] = datetime.now().isoformat()
            _save_pending(pending)
            return reply
    return {}


def mark_published(reply_id: str):
    """Marca un reply como publicado."""
    pending = _load_pending()
    for reply in pending:
        if reply.get("reply_id") == reply_id:
            reply["estado"] = "published"
            reply["published_at"] = datetime.now().isoformat()
    _save_pending(pending)


def get_pending() -> list:
    """Retorna todos los replies pendientes de aprobación."""
    pending = _load_pending()
    return [p for p in pending if p.get("estado") == "pending_approval"]
