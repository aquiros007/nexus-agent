"""
publishers/facebook.py
Facebook Page publisher — Nexus IQ Agent
Cubre: posts, imágenes, videos, comentarios, Messenger.

STATUS: Listo. Se activa con App Review aprobado de Meta.
"""
import os
from datetime import datetime, timezone
from publishers.meta_client import get, post, _page_id, is_configured
from dotenv import load_dotenv

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


# ────────────────────────────────────────
# PUBLICACIÓN DE CONTENIDO
# ────────────────────────────────────────

def publish_text_post(message: str) -> dict:
    """Publica post de texto en la Facebook Page."""
    if DRY_RUN:
        print(f"[DRY-RUN][FB] Post texto: {message[:80]}...")
        return {"id": "dry-run-fb-post"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    result = post(f"{_page_id()}/feed", {"message": message})
    print(f"[FB] Post publicado: {result.get('id')}")
    return result


def publish_photo_post(message: str, image_url: str) -> dict:
    """Publica post con imagen en la Facebook Page."""
    if DRY_RUN:
        print(f"[DRY-RUN][FB] Post imagen: {message[:60]}... | {image_url}")
        return {"id": "dry-run-fb-photo"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    result = post(f"{_page_id()}/photos", {
        "message": message,
        "url": image_url
    })
    print(f"[FB] Foto publicada: {result.get('id')}")
    return result


def publish_video_post(message: str, video_url: str, title: str = "") -> dict:
    """
    Publica video/Reel en Facebook Page.
    Meta descarga el video desde video_url (debe ser URL pública accesible).
    """
    if DRY_RUN:
        print(f"[DRY-RUN][FB] Video: {title or message[:60]}... | {video_url}")
        return {"id": "dry-run-fb-video"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    data = {"description": message, "file_url": video_url}
    if title:
        data["title"] = title

    result = post(f"{_page_id()}/videos", data)
    print(f"[FB] Video publicado: {result.get('id')}")
    return result


# ────────────────────────────────────────
# LECTURA DE COMENTARIOS
# ────────────────────────────────────────

def get_page_comments(limit: int = 50, since_hours: int = 48) -> list:
    """
    Lee comentarios recientes de la Page.
    Requiere: pages_read_engagement (nivel estándar — disponible sin App Review)
    """
    if not is_configured():
        print("[FB] Meta no configurado — retornando lista vacía")
        return []

    from datetime import timedelta
    since_ts = int(
        (datetime.now(timezone.utc) - timedelta(hours=since_hours)).timestamp()
    )

    data = get(f"{_page_id()}/feed", {
        "fields": "id,message,created_time,from,comments{id,message,from,created_time}",
        "limit": limit,
        "since": since_ts
    })

    comments = []
    for post_item in data.get("data", []):
        for comment in post_item.get("comments", {}).get("data", []):
            comments.append({
                "interaction_id": f"fb_comment_{comment['id']}",
                "canal": "facebook",
                "tipo": "comment",
                "post_id": post_item["id"],
                "comment_id": comment["id"],
                "usuario": comment.get("from", {}).get("name", "unknown"),
                "usuario_id": comment.get("from", {}).get("id", ""),
                "texto": comment.get("message", ""),
                "timestamp": comment.get("created_time", "")
            })

    print(f"[FB] {len(comments)} comentarios leídos")
    return comments


def reply_to_comment(comment_id: str, message: str) -> dict:
    """
    Responde un comentario en la Page.
    Requiere: pages_manage_engagement (nivel estándar)
    """
    if DRY_RUN:
        print(f"[DRY-RUN][FB] Reply a {comment_id}: {message[:80]}...")
        return {"id": "dry-run-fb-reply"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    result = post(f"{comment_id}/comments", {"message": message})
    print(f"[FB] Reply publicado en comentario {comment_id}")
    return result


# ────────────────────────────────────────
# MESSENGER
# ────────────────────────────────────────

def get_messenger_conversations(limit: int = 20) -> list:
    """
    Lee conversaciones de Messenger.
    Requiere: pages_messaging (AVANZADO — necesita App Review)
    NOTA: Solo se puede responder dentro de 24h del último mensaje del usuario.
    """
    if not is_configured():
        return []

    data = get(f"{_page_id()}/conversations", {
        "platform": "messenger",
        "fields": "id,updated_time,messages{id,message,from,created_time}",
        "limit": limit
    })

    conversations = []
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=23)

    for conv in data.get("data", []):
        messages = conv.get("messages", {}).get("data", [])
        if not messages:
            continue

        last_msg = messages[0]  # El más reciente

        # Calcular si está dentro de la ventana de 24h
        try:
            msg_time = datetime.fromisoformat(
                last_msg["created_time"].replace("Z", "+00:00")
            )
            hours_elapsed = (datetime.now(timezone.utc) - msg_time).seconds // 3600
            within_window = msg_time > cutoff
        except Exception:
            hours_elapsed = 99
            within_window = False

        # Solo incluir si es del usuario (no de la Page)
        from_page = last_msg.get("from", {}).get("id") == _page_id()
        if from_page:
            continue

        conversations.append({
            "interaction_id": f"fb_messenger_{conv['id']}",
            "canal": "facebook",
            "tipo": "messenger",
            "conversation_id": conv["id"],
            "message_id": last_msg["id"],
            "usuario": last_msg.get("from", {}).get("name", "unknown"),
            "usuario_id": last_msg.get("from", {}).get("id", ""),
            "texto": last_msg.get("message", ""),
            "timestamp": last_msg.get("created_time", ""),
            "horas_transcurridas": hours_elapsed,
            "dentro_ventana_24h": within_window,
            "alerta_ventana": hours_elapsed >= 20 and within_window
        })

    print(f"[FB] {len(conversations)} conversaciones de Messenger leídas")
    return conversations


def send_messenger_reply(conversation_id: str, message: str) -> dict:
    """
    Envía mensaje por Messenger.
    Requiere: pages_messaging (AVANZADO — necesita App Review)
    """
    if DRY_RUN:
        print(f"[DRY-RUN][FB/Messenger] Reply a conv {conversation_id}: {message[:80]}...")
        return {"message_id": "dry-run-messenger"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    result = post(f"{_page_id()}/messages", {
        "recipient": {"thread_key": conversation_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    })
    print(f"[FB/Messenger] Mensaje enviado en conversación {conversation_id}")
    return result
