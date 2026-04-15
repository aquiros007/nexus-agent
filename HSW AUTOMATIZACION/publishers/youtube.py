"""
publishers/youtube.py
YouTube Data API v3 — Nexus IQ Agent
STATUS: Listo. Pendiente configuración Google Cloud Console.
El refresh token no expira mientras se use regularmente.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

YT_API = "https://www.googleapis.com/youtube/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

_access_token_cache = {"token": None}


def is_configured() -> bool:
    return bool(
        os.getenv("YOUTUBE_CLIENT_ID", "") not in ("", "REEMPLAZAR")
        and os.getenv("YOUTUBE_REFRESH_TOKEN", "") not in ("", "REEMPLAZAR")
    )


def _get_access_token() -> str:
    """Obtiene access token usando refresh token. Cachea en memoria."""
    if _access_token_cache["token"]:
        return _access_token_cache["token"]

    r = requests.post(TOKEN_URL, data={
        "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
        "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
        "refresh_token": os.getenv("YOUTUBE_REFRESH_TOKEN"),
        "grant_type": "refresh_token"
    }, timeout=30)
    r.raise_for_status()
    token = r.json()["access_token"]
    _access_token_cache["token"] = token
    return token


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_access_token()}"}


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list = None,
    category_id: str = "28",   # 28 = Science & Technology
    privacy: str = "private"   # private | unlisted | public
) -> dict:
    """
    Sube un video a YouTube.
    video_path: ruta local al archivo .mp4
    Empieza con privacy='private' para revisar antes de publicar.
    """
    if DRY_RUN:
        print(f"[DRY-RUN][YT] Video: {title[:60]}... | privacy: {privacy}")
        return {"id": "dry-run-yt-video"}

    if not is_configured():
        return {"error": "YouTube no configurado — pendiente Google Cloud Console"}

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=_get_access_token(),
        refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        token_uri=TOKEN_URL
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["IA", "InteligenciaArtificial", "NexusIQ", "LATAM", "Shorts"],
            "categoryId": category_id
        },
        "status": {"privacyStatus": privacy}
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    print(f"[YT] Video subido: https://youtube.com/watch?v={video_id}")
    return {"id": video_id, "url": f"https://youtube.com/watch?v={video_id}"}


def get_video_comments(video_id: str, limit: int = 20) -> list:
    """Lee comentarios de un video de YouTube."""
    if not is_configured():
        return []

    r = requests.get(f"{YT_API}/commentThreads", params={
        "part": "snippet",
        "videoId": video_id,
        "maxResults": limit,
        "order": "time"
    }, headers=_headers(), timeout=30)

    if r.status_code != 200:
        return []

    comments = []
    for item in r.json().get("items", []):
        top = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "interaction_id": f"yt_comment_{item['id']}",
            "canal": "youtube",
            "tipo": "comment",
            "video_id": video_id,
            "comment_id": item["id"],
            "usuario": top.get("authorDisplayName", "unknown"),
            "texto": top.get("textDisplay", ""),
            "timestamp": top.get("publishedAt", ""),
            "likes": top.get("likeCount", 0)
        })

    print(f"[YT] {len(comments)} comentarios leídos del video {video_id}")
    return comments


def reply_to_comment(parent_id: str, text: str) -> dict:
    """Responde un comentario de YouTube."""
    if DRY_RUN:
        print(f"[DRY-RUN][YT] Reply a {parent_id}: {text[:80]}...")
        return {"id": "dry-run-yt-reply"}

    if not is_configured():
        return {"error": "YouTube no configurado"}

    r = requests.post(f"{YT_API}/comments", params={"part": "snippet"},
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "snippet": {
                "parentId": parent_id,
                "textOriginal": text
            }
        }, timeout=30
    )
    r.raise_for_status()
    result = r.json()
    print(f"[YT] Reply publicado: {result.get('id')}")
    return result
