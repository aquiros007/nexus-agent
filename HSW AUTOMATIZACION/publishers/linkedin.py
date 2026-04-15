"""
publishers/linkedin.py
LinkedIn REST API (moderna, versionada) — Nexus IQ Agent
STATUS: Listo para usar — token disponible.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

LI_REST = "https://api.linkedin.com/rest"
LI_VERSION = "202503"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def _headers() -> dict:
    token = os.getenv("LI_ACCESS_TOKEN", "")
    if not token or token == "REEMPLAZAR":
        raise RuntimeError("LI_ACCESS_TOKEN no configurado")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LI_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
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

def _post_payload(text: str, visibility: str = "PUBLIC", content: dict = None) -> dict:
    payload = {
        "author": _person_urn(),
        "commentary": text,
        "visibility": visibility.upper(),
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if content:
        payload["content"] = content
    return payload


def publish_text_post(text: str, visibility: str = "PUBLIC") -> dict:
    """Publica post de texto en LinkedIn."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post: {text[:80]}...")
        return {"id": "dry-run-li-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    r = requests.post(
        f"{LI_REST}/posts", json=_post_payload(text, visibility),
        headers=_headers(), timeout=30
    )
    if r.status_code == 401:
        raise PermissionError("TOKEN_EXPIRADO: Renovar LI_ACCESS_TOKEN")
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", "")
    print(f"[LI] Post publicado: {post_id}")
    return {"id": post_id}


def publish_post_with_image(text: str, image_url: str, title: str = "") -> dict:
    """Publica post con imagen desde URL."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post con imagen: {text[:60]}...")
        return {"id": "dry-run-li-image-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    # Paso 1: inicializar upload de imagen
    init_payload = {"initializeUploadRequest": {"owner": _person_urn()}}
    r1 = requests.post(
        f"{LI_REST}/images?action=initializeUpload",
        json=init_payload, headers=_headers(), timeout=30
    )
    if r1.status_code == 401:
        raise PermissionError("TOKEN_EXPIRADO: Renovar LI_ACCESS_TOKEN")
    r1.raise_for_status()
    data = r1.json().get("value", {})
    upload_url = data["uploadUrl"]
    image_urn = data["image"]

    # Paso 2: descargar imagen y subir a LinkedIn
    img_response = requests.get(image_url, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"})
    img_response.raise_for_status()
    requests.put(upload_url, data=img_response.content,
                 headers={"Content-Type": "application/octet-stream"}, timeout=60)

    # Paso 3: publicar post con imagen
    content = {"media": {"id": image_urn}}
    r = requests.post(
        f"{LI_REST}/posts", json=_post_payload(text, content=content),
        headers=_headers(), timeout=30
    )
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", "")
    print(f"[LI] Post con imagen publicado: {post_id} (image: {image_urn})")
    return {"id": post_id, "image_urn": image_urn}


def publish_post_with_image_file(text: str, image_path: str) -> dict:
    """Publica post con imagen desde archivo local."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post con imagen local: {text[:60]}...")
        return {"id": "dry-run-li-image-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    # Paso 1: inicializar upload
    init_payload = {"initializeUploadRequest": {"owner": _person_urn()}}
    r1 = requests.post(
        f"{LI_REST}/images?action=initializeUpload",
        json=init_payload, headers=_headers(), timeout=30
    )
    if r1.status_code == 401:
        raise PermissionError("TOKEN_EXPIRADO: Renovar LI_ACCESS_TOKEN")
    r1.raise_for_status()
    data = r1.json().get("value", {})
    upload_url = data["uploadUrl"]
    image_urn = data["image"]

    # Paso 2: subir archivo
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    requests.put(upload_url, data=img_bytes,
                 headers={"Content-Type": "application/octet-stream"}, timeout=60)

    # Paso 3: publicar
    content = {"media": {"id": image_urn}}
    r = requests.post(
        f"{LI_REST}/posts", json=_post_payload(text, content=content),
        headers=_headers(), timeout=30
    )
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", "")
    print(f"[LI] Post con imagen local publicado: {post_id} (image: {image_urn})")
    return {"id": post_id, "image_urn": image_urn}


def publish_post_with_document(caption: str, pdf_path: str, title: str = "") -> dict:
    """Publica post con documento PDF (carrusel)."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Post con PDF: {caption[:60]}...")
        return {"id": "dry-run-li-doc-post"}

    if not is_configured():
        return {"error": "LinkedIn no configurado"}

    # Paso 1: inicializar upload de documento
    init_payload = {"initializeUploadRequest": {"owner": _person_urn()}}
    r1 = requests.post(
        f"{LI_REST}/documents?action=initializeUpload",
        json=init_payload, headers=_headers(), timeout=30
    )
    if r1.status_code == 401:
        raise PermissionError("TOKEN_EXPIRADO: Renovar LI_ACCESS_TOKEN")
    r1.raise_for_status()
    data = r1.json().get("value", {})
    upload_url = data["uploadUrl"]
    doc_urn = data["document"]

    # Paso 2: subir PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    requests.put(upload_url, data=pdf_bytes,
                 headers={"Content-Type": "application/octet-stream"}, timeout=60)

    # Paso 3: publicar con documento
    content = {"media": {"title": title or "Nexus IQ Strategies", "id": doc_urn}}
    r = requests.post(
        f"{LI_REST}/posts", json=_post_payload(caption, content=content),
        headers=_headers(), timeout=30
    )
    r.raise_for_status()
    post_id = r.headers.get("x-restli-id", "")
    print(f"[LI] Post con documento publicado: {post_id} (doc: {doc_urn})")
    return {"id": post_id, "document_urn": doc_urn}


def delete_post(post_id: str) -> bool:
    """Elimina un post de LinkedIn."""
    if DRY_RUN:
        print(f"[DRY-RUN][LI] Delete: {post_id}")
        return True
    r = requests.delete(f"{LI_REST}/posts/{post_id}", headers=_headers(), timeout=30)
    if r.status_code == 204:
        print(f"[LI] Post eliminado: {post_id}")
        return True
    print(f"[LI] Error eliminando post {post_id}: {r.status_code}")
    return False


# ────────────────────────────────────────
# LECTURA Y RESPUESTA
# ────────────────────────────────────────

def get_post_comments(post_id: str) -> list:
    """Lee comentarios de un post de LinkedIn."""
    if not is_configured():
        return []

    r = requests.get(
        f"{LI_REST}/socialActions/{post_id}/comments",
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
        f"{LI_REST}/socialActions/{post_id}/comments",
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
