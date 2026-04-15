"""
publishers/tiktok.py
TikTok Content Posting API — Nexus IQ Agent
STATUS: Listo. Pendiente aprobación TikTok Developer Portal.
"""
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

TIKTOK_API = "https://open.tiktokapis.com/v2"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def _headers() -> dict:
    token = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    if not token or token == "REEMPLAZAR":
        raise RuntimeError("TIKTOK_ACCESS_TOKEN no configurado")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8"
    }


def is_configured() -> bool:
    return bool(
        os.getenv("TIKTOK_ACCESS_TOKEN", "") not in ("", "REEMPLAZAR")
    )


def refresh_token() -> str:
    """Renueva el access token usando el refresh token (expira en 24h)."""
    r = requests.post(f"{TIKTOK_API}/oauth/token/", json={
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("TIKTOK_REFRESH_TOKEN")
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    new_token = data["data"]["access_token"]
    print(f"[TT] Token renovado exitosamente")
    return new_token


def publish_video(
    video_url: str,
    title: str,
    privacy: str = "SELF_ONLY"
) -> dict:
    """
    Publica video en TikTok via URL (Pull from URL).
    privacy: SELF_ONLY | MUTUAL_FOLLOW_FRIENDS | FOLLOWER_OF_CREATOR | PUBLIC_TO_EVERYONE
    Empieza con SELF_ONLY para testing.
    """
    if DRY_RUN:
        print(f"[DRY-RUN][TT] Video: {title[:60]}... | privacy: {privacy}")
        return {"publish_id": "dry-run-tt-video"}

    if not is_configured():
        return {"error": "TikTok no configurado — pendiente Developer Portal"}

    # Paso 1: iniciar publicación
    payload = {
        "post_info": {
            "title": title[:150],
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url
        }
    }

    r = requests.post(
        f"{TIKTOK_API}/post/publish/video/init/",
        json=payload, headers=_headers(), timeout=30
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    publish_id = data.get("publish_id")
    print(f"[TT] Publicación iniciada: {publish_id}")

    # Paso 2: verificar estado
    _poll_publish_status(publish_id)
    return {"publish_id": publish_id}


def _poll_publish_status(publish_id: str, max_attempts: int = 12):
    """Verifica el estado de publicación de TikTok."""
    for i in range(max_attempts):
        r = requests.post(
            f"{TIKTOK_API}/post/publish/status/fetch/",
            json={"publish_id": publish_id},
            headers=_headers(), timeout=30
        )
        if r.status_code == 200:
            status = r.json().get("data", {}).get("status", "")
            if status == "PUBLISH_COMPLETE":
                print(f"[TT] Publicación completada: {publish_id}")
                return
            if status in ("FAILED", "CANCELLED"):
                print(f"[TT] ERROR publicando {publish_id}: {status}")
                return
        time.sleep(10)
    print(f"[TT] WARN: Timeout verificando publicación {publish_id}")


def get_comments(video_id: str, limit: int = 20) -> list:
    """Lee comentarios de un video de TikTok."""
    if not is_configured():
        return []

    r = requests.get(
        f"{TIKTOK_API}/research/video/comment/list/",
        params={"video_id": video_id, "max_count": limit},
        headers=_headers(), timeout=30
    )
    if r.status_code != 200:
        return []

    comments = []
    for item in r.json().get("data", {}).get("comments", []):
        comments.append({
            "interaction_id": f"tt_comment_{item.get('id')}",
            "canal": "tiktok",
            "tipo": "comment",
            "video_id": video_id,
            "comment_id": item.get("id"),
            "usuario": item.get("username", "unknown"),
            "texto": item.get("text", ""),
            "timestamp": str(item.get("create_time", ""))
        })
    return comments
