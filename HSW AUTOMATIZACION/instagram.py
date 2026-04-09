"""
publishers/instagram.py
Instagram Business publisher — Nexus IQ Agent
Mismo token que Facebook. Endpoints distintos.

STATUS: Listo. Se activa con App Review aprobado de Meta.
Permisos: instagram_content_publish, instagram_manage_comments
"""
import os
import time
from publishers.meta_client import get, post, _ig_id, is_configured
from dotenv import load_dotenv

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


# ────────────────────────────────────────
# PUBLICACIÓN
# ────────────────────────────────────────

def publish_photo(caption: str, image_url: str) -> dict:
    """
    Publica foto en Instagram.
    Flujo: crear contenedor → publicar.
    image_url debe ser URL pública (Meta la descarga).
    """
    if DRY_RUN:
        print(f"[DRY-RUN][IG] Foto: {caption[:60]}...")
        return {"id": "dry-run-ig-photo"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    # Paso 1: crear contenedor de media
    container = post(f"{_ig_id()}/media", {
        "image_url": image_url,
        "caption": caption
    })
    container_id = container.get("id")
    print(f"[IG] Contenedor creado: {container_id}")

    # Paso 2: esperar procesamiento Meta (hasta 30s)
    _wait_for_container(container_id)

    # Paso 3: publicar
    result = post(f"{_ig_id()}/media_publish", {
        "creation_id": container_id
    })
    print(f"[IG] Foto publicada: {result.get('id')}")
    return result


def publish_reel(caption: str, video_url: str) -> dict:
    """
    Publica Reel en Instagram.
    video_url: URL pública del video (MP4, máx 15 min, recomendado <90s para Reel).
    """
    if DRY_RUN:
        print(f"[DRY-RUN][IG] Reel: {caption[:60]}...")
        return {"id": "dry-run-ig-reel"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    # Paso 1: contenedor de Reel
    container = post(f"{_ig_id()}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": True
    })
    container_id = container.get("id")
    print(f"[IG] Contenedor Reel creado: {container_id}")

    # Paso 2: esperar (los videos tardan más)
    _wait_for_container(container_id, max_wait=120)

    # Paso 3: publicar
    result = post(f"{_ig_id()}/media_publish", {
        "creation_id": container_id
    })
    print(f"[IG] Reel publicado: {result.get('id')}")
    return result


def publish_carousel(caption: str, image_urls: list) -> dict:
    """
    Publica carrusel de imágenes.
    image_urls: lista de URLs públicas (máx 10).
    """
    if DRY_RUN:
        print(f"[DRY-RUN][IG] Carrusel {len(image_urls)} imágenes: {caption[:60]}...")
        return {"id": "dry-run-ig-carousel"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    # Paso 1: crear contenedor por cada imagen
    children_ids = []
    for url in image_urls[:10]:
        child = post(f"{_ig_id()}/media", {
            "image_url": url,
            "is_carousel_item": True
        })
        children_ids.append(child["id"])

    # Paso 2: contenedor carrusel
    container = post(f"{_ig_id()}/media", {
        "media_type": "CAROUSEL",
        "caption": caption,
        "children": ",".join(children_ids)
    })
    container_id = container.get("id")
    _wait_for_container(container_id)

    # Paso 3: publicar
    result = post(f"{_ig_id()}/media_publish", {
        "creation_id": container_id
    })
    print(f"[IG] Carrusel publicado: {result.get('id')}")
    return result


def _wait_for_container(container_id: str, max_wait: int = 60):
    """Espera que Meta procese el contenedor antes de publicar."""
    for _ in range(max_wait // 5):
        status = get(container_id, {"fields": "status_code"})
        code = status.get("status_code", "")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise RuntimeError(f"[IG] Error procesando contenedor {container_id}")
        time.sleep(5)
    print(f"[IG] WARN: Timeout esperando contenedor {container_id}")


# ────────────────────────────────────────
# LECTURA DE COMENTARIOS
# ────────────────────────────────────────

def get_recent_comments(limit: int = 50) -> list:
    """
    Lee comentarios recientes de posts de Instagram.
    Requiere: instagram_manage_comments (AVANZADO — App Review)
    """
    if not is_configured():
        return []

    media_data = get(f"{_ig_id()}/media", {
        "fields": "id,caption,timestamp,comments{id,text,username,timestamp}",
        "limit": 10
    })

    comments = []
    for media in media_data.get("data", []):
        for comment in media.get("comments", {}).get("data", []):
            comments.append({
                "interaction_id": f"ig_comment_{comment['id']}",
                "canal": "instagram",
                "tipo": "comment",
                "media_id": media["id"],
                "comment_id": comment["id"],
                "usuario": comment.get("username", "unknown"),
                "texto": comment.get("text", ""),
                "timestamp": comment.get("timestamp", "")
            })

    print(f"[IG] {len(comments)} comentarios leídos")
    return comments[:limit]


def reply_to_comment(comment_id: str, message: str) -> dict:
    """
    Responde un comentario de Instagram.
    Requiere: instagram_manage_comments (AVANZADO — App Review)
    """
    if DRY_RUN:
        print(f"[DRY-RUN][IG] Reply a {comment_id}: {message[:80]}...")
        return {"id": "dry-run-ig-reply"}

    if not is_configured():
        return {"error": "Meta no configurado — pendiente App Review"}

    result = post(f"{comment_id}/replies", {"message": message})
    print(f"[IG] Reply publicado en comentario {comment_id}")
    return result
