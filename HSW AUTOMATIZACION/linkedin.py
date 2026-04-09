"""
publishers/linkedin.py
LinkedIn UGC Posts API — Nexus IQ Agent
STATUS: Listo para usar — token disponible.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

LI_API = "https://api.linkedin.com/v2"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def _headers() -> dict:
    token = os.getenv("LI_ACCESS_TOKEN", "")
    if not token or token == "REEMPLAZAR":
        raise RuntimeError("LI_ACCESS_TOKEN no configurado")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }


def _person_urn() -> str:
    return os.getenv("LI_PERSON_URN", "")


def is_configured() -> bool:
    token = os.getenv("LI_ACCESS_TOKEN", "")
    urn = os.getenv("LI_PERSON_URN", "")
    return bool(token and urn and token != "REEMPLAZAR")


# ────────────────────────────────────────
# PUBLICACIÓN
# ────────────────────────────────────────

def publish_text_post(text: str, visibility: str = "PUBLIC") -> dict:
    """Publica post de texto en LinkedIn."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post: {text[:80]}...")
        return {"id": "dry-run-li-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    payload = {
        "author": _person_urn(),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility
        }
    }

    r = requests.post(f"{LI_API}/ugcPosts", json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", r.json().get("id", ""))
    print(f"[LI] Post publicado: {post_id}")
    return {"id": post_id}


def publish_post_with_image(text: str, image_url: str, title: str = "") -> dict:
    """
    Publica post con imagen. 
    Requiere flujo: register upload → upload → crear post.
    """
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post con imagen: {text[:60]}...")
        return {"id": "dry-run-li-image-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    # Paso 1: registrar upload
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": _person_urn(),
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    r = requests.post(
        f"{LI_API}/assets?action=registerUpload",
        json=register_payload, headers=_headers(), timeout=30
    )
    r.raise_for_status()
    data = r.json()
    asset_urn = data["value"]["asset"]
    upload_url = data["value"]["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]

    # Paso 2: descargar imagen y subir
    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()
    upload_headers = {k: v for k, v in _headers().items() if k != "Content-Type"}
    upload_headers["Content-Type"] = "image/jpeg"
    requests.put(upload_url, data=img_response.content, headers=upload_headers, timeout=60)

    # Paso 3: crear post
    payload = {
        "author": _person_urn(),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "description": {"text": title or text[:100]},
                    "media": asset_urn,
                    "title": {"text": title or ""}
                }]
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    r = requests.post(f"{LI_API}/ugcPosts", json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", "")
    print(f"[LI] Post con imagen publicado: {post_id}")
    return {"id": post_id}


# ────────────────────────────────────────
# LECTURA Y RESPUESTA
# ────────────────────────────────────────

def get_post_comments(post_id: str) -> list:
    """Lee comentarios de un post de LinkedIn."""
    if not is_configured():
        return []

    r = requests.get(
        f"{LI_API}/socialActions/{post_id}/comments",
        headers=_headers(), timeout=30
    )
    if r.status_code != 200:
        return []

    data = r.json()
    comments = []
    for item in data.get("elements", []):
        comments.append({
            "interaction_id": f"li_comment_{item.get('id', '')}",
            "canal": "linkedin",
            "tipo": "comment",
            "comment_id": item.get("id", ""),
            "post_id": post_id,
            "usuario": item.get("actor", "").replace("urn:li:person:", "@"),
            "texto": item.get("message", {}).get("text", ""),
            "timestamp": str(item.get("created", {}).get("time", ""))
        })

    print(f"[LI] {len(comments)} comentarios leídos del post {post_id}")
    return comments


def reply_to_comment(post_id: str, comment_id: str, text: str) -> dict:
    """Responde un comentario de LinkedIn."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Reply a {comment_id}: {text[:80]}...")
        return {"id": "dry-run-li-reply"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    payload = {
        "actor": _person_urn(),
        "message": {"text": text},
        "parentComment": comment_id
    }
    r = requests.post(
        f"{LI_API}/socialActions/{post_id}/comments",
        json=payload, headers=_headers(), timeout=30
    )
    r.raise_for_status()
    print(f"[LI] Reply publicado en comentario {comment_id}")
    return r.json()


def get_messages() -> list:
    """
    Lee mensajes directos de LinkedIn.
    Nota: La API de mensajería directa de LinkedIn es muy limitada
    para uso automatizado. Se retorna lista vacía hasta tener acceso.
    """
    print("[LI] WARN: LinkedIn Messaging API requiere acceso especial de partner.")
    return []
