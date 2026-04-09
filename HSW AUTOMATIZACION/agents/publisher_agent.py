"""
agents/publisher_agent.py
Único agente con acceso de escritura a las 5 APIs.
Solo publica contenido y respuestas explícitamente aprobadas.
"""
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "./data"
LOG_FILE = f"{DATA_DIR}/published_log.json"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def _load_log() -> list:
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _append_log(entry: dict):
    log = _load_log()
    log.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def publish_content(item: dict) -> dict:
    """
    Publica un item de contenido aprobado en sus canales.
    item debe tener 'drafts', 'approved_channels', 'item_id'.
    """
    results = {}
    channels = item.get("approved_channels", [])
    drafts = item.get("drafts", {})

    for canal in channels:
        draft_data = drafts.get(canal, {})
        draft_text = draft_data.get("draft", "")

        if not draft_text:
            print(f"[PUB] Sin draft para {canal} — skipping")
            continue

        try:
            result = _publish_to_channel(canal, draft_text, item)
            results[canal] = result

            log_entry = {
                "type": "content",
                "item_id": item.get("item_id"),
                "canal": canal,
                "post_id": result.get("id", result.get("publish_id", "")),
                "title": item.get("title", "")[:80],
                "published_at": datetime.now().isoformat(),
                "dry_run": DRY_RUN
            }
            _append_log(log_entry)

            # Actualizar estado en content_agent
            from agents.content_agent import mark_published
            mark_published(
                item.get("item_id"),
                canal,
                result.get("id", result.get("publish_id", "dry-run"))
            )

        except Exception as e:
            print(f"[PUB] Error publicando en {canal}: {e}")
            results[canal] = {"error": str(e)}

    return results


def publish_reply(reply: dict) -> dict:
    """
    Publica una respuesta aprobada en el canal correspondiente.
    """
    canal = reply.get("canal")
    tipo = reply.get("tipo")
    draft = reply.get("draft", "")

    if not draft:
        return {"error": "Draft vacío"}

    try:
        result = _publish_reply_to_channel(canal, tipo, reply, draft)

        log_entry = {
            "type": "reply",
            "reply_id": reply.get("reply_id"),
            "canal": canal,
            "usuario": reply.get("usuario"),
            "post_id": result.get("id", ""),
            "published_at": datetime.now().isoformat(),
            "dry_run": DRY_RUN
        }
        _append_log(log_entry)

        # Actualizar estado en responder_agent
        from agents.responder_agent import mark_published
        mark_published(reply.get("reply_id"))

        # Actualizar lead como contactado si tiene lead_id
        if reply.get("lead_id"):
            try:
                from integrations.sheets_client import update_lead_status
                update_lead_status(reply["lead_id"], "Contactado")
            except Exception as e:
                print(f"[PUB] Warn: no se pudo actualizar lead en Sheets: {e}")

        return result

    except Exception as e:
        print(f"[PUB] Error publicando reply en {canal}/{tipo}: {e}")
        return {"error": str(e)}


def _publish_to_channel(canal: str, text: str, item: dict) -> dict:
    """Router de publicación de contenido por canal."""

    if canal == "facebook":
        from publishers.facebook import publish_text_post
        return publish_text_post(text)

    elif canal == "instagram":
        from publishers.instagram import publish_photo
        # Para Reel/foto se necesita image_url — por ahora text post simulado
        # En producción: generar imagen o usar URL de asset
        image_url = item.get("image_url", "")
        if image_url:
            return publish_photo(text, image_url)
        if DRY_RUN:
            print(f"[DRY-RUN][IG] Caption: {text[:80]}... (sin imagen — agregar image_url)")
            return {"id": "dry-run-ig-no-image"}
        return {"error": "Instagram requiere image_url para publicar"}

    elif canal == "tiktok":
        from publishers.tiktok import publish_video
        video_url = item.get("video_url", "")
        title = item.get("title", text[:150])
        if video_url:
            return publish_video(video_url, title, privacy="SELF_ONLY")
        if DRY_RUN:
            print(f"[DRY-RUN][TT] Script: {text[:80]}... (sin video_url)")
            return {"publish_id": "dry-run-tt-no-video"}
        return {"error": "TikTok requiere video_url"}

    elif canal == "youtube":
        from publishers.youtube import upload_video
        video_path = item.get("video_path", "")
        if video_path:
            return upload_video(
                video_path=video_path,
                title=item.get("title", "")[:100],
                description=text,
                privacy="private"
            )
        if DRY_RUN:
            print(f"[DRY-RUN][YT] Descripción: {text[:80]}... (sin video_path)")
            return {"id": "dry-run-yt-no-video"}
        return {"error": "YouTube requiere video_path"}

    elif canal == "linkedin":
        from publishers.linkedin import publish_text_post
        return publish_text_post(text)

    return {"error": f"Canal desconocido: {canal}"}


def _publish_reply_to_channel(canal: str, tipo: str, reply: dict, text: str) -> dict:
    """Router de publicación de replies por canal y tipo."""

    if canal == "facebook":
        if tipo == "comment":
            from publishers.facebook import reply_to_comment
            return reply_to_comment(reply.get("comment_id", ""), text)
        elif tipo == "messenger":
            from publishers.facebook import send_messenger_reply
            return send_messenger_reply(reply.get("conversation_id", ""), text)

    elif canal == "instagram":
        from publishers.instagram import reply_to_comment
        return reply_to_comment(reply.get("comment_id", ""), text)

    elif canal == "tiktok":
        # TikTok no tiene reply API pública estable aún
        if DRY_RUN:
            print(f"[DRY-RUN][TT] Reply: {text[:80]}...")
            return {"id": "dry-run-tt-reply"}
        return {"error": "TikTok reply API no disponible aún"}

    elif canal == "youtube":
        from publishers.youtube import reply_to_comment
        return reply_to_comment(reply.get("comment_id", ""), text)

    elif canal == "linkedin":
        from publishers.linkedin import reply_to_comment
        return reply_to_comment(
            reply.get("post_id", ""),
            reply.get("comment_id", ""),
            text
        )

    return {"error": f"Canal/tipo no manejado: {canal}/{tipo}"}
