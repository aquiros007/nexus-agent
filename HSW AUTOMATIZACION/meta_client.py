"""
publishers/meta_client.py
Cliente base Meta Graph API v21 — compartido por facebook.py e instagram.py
Un solo Page Access Token cubre ambas plataformas.

STATUS: Código listo. Se activa cuando Meta apruebe el App Review.
Permisos requeridos:
  - pages_manage_posts
  - pages_read_engagement
  - pages_manage_engagement
  - instagram_content_publish
  - instagram_manage_comments
  - pages_messaging
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _token() -> str:
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    if not token or token == "REEMPLAZAR":
        raise RuntimeError(
            "FB_PAGE_ACCESS_TOKEN no configurado. "
            "Pendiente App Review de Meta."
        )
    return token


def _page_id() -> str:
    return os.getenv("FB_PAGE_ID", "")


def _ig_id() -> str:
    return os.getenv("IG_BUSINESS_ACCOUNT_ID", "")


def get(endpoint: str, params: dict = None) -> dict:
    """GET a Meta Graph API."""
    url = f"{GRAPH_BASE}/{endpoint}"
    p = {"access_token": _token()}
    if params:
        p.update(params)
    r = requests.get(url, params=p, timeout=30)
    r.raise_for_status()
    return r.json()


def post(endpoint: str, data: dict = None, files: dict = None) -> dict:
    """POST a Meta Graph API."""
    url = f"{GRAPH_BASE}/{endpoint}"
    d = {"access_token": _token()}
    if data:
        d.update(data)
    r = requests.post(url, data=d, files=files, timeout=60)
    r.raise_for_status()
    return r.json()


def is_configured() -> bool:
    """Verifica si los tokens Meta están configurados."""
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    page_id = os.getenv("FB_PAGE_ID", "")
    return bool(token and page_id and token != "REEMPLAZAR")
