"""
agents/engagement_agent.py
Lee comentarios, DMs y mensajes de los 5 canales.
Clasifica intención via Claude. Alimenta lead_agent y responder_agent.
"""
import json
import os
from datetime import datetime
from integrations.claude_client import classify_interaction
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "./data"
INTERACTIONS_FILE = f"{DATA_DIR}/interactions.json"


def _load_seen() -> set:
    """Carga IDs de interacciones ya procesadas para evitar duplicados."""
    path = f"{DATA_DIR}/seen_items.json"
    try:
        with open(path) as f:
            data = json.load(f)
            return set(i for i in data if i.startswith("interaction_"))
    except Exception:
        return set()


def _mark_seen(interaction_id: str):
    path = f"{DATA_DIR}/seen_items.json"
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        data = []
    if interaction_id not in data:
        data.append(interaction_id)
    with open(path, "w") as f:
        json.dump(data, f)


def _collect_facebook_interactions() -> list:
    """Recolecta comentarios y mensajes de Facebook."""
    try:
        from publishers.facebook import get_page_comments, get_messenger_conversations
        items = []
        items.extend(get_page_comments(limit=30, since_hours=48))
        items.extend(get_messenger_conversations(limit=20))
        return items
    except RuntimeError as e:
        print(f"[ENGAGE][FB] Skipped: {e}")
        return []
    except Exception as e:
        print(f"[ENGAGE][FB] Error: {e}")
        return []


def _collect_instagram_interactions() -> list:
    """Recolecta comentarios de Instagram."""
    try:
        from publishers.instagram import get_recent_comments
        return get_recent_comments(limit=30)
    except RuntimeError as e:
        print(f"[ENGAGE][IG] Skipped: {e}")
        return []
    except Exception as e:
        print(f"[ENGAGE][IG] Error: {e}")
        return []


def _collect_tiktok_interactions() -> list:
    """Recolecta comentarios de TikTok (requiere video IDs recientes)."""
    try:
        from publishers.tiktok import get_comments, is_configured
        if not is_configured():
            print("[ENGAGE][TT] No configurado — skipping")
            return []

        # Lee log de videos publicados para obtener IDs
        log_path = f"{DATA_DIR}/published_log.json"
        try:
            with open(log_path) as f:
                log = json.load(f)
            tt_videos = [
                e["post_id"] for e in log
                if e.get("canal") == "tiktok" and e.get("post_id")
            ][-5:]  # Últimos 5 videos
        except Exception:
            tt_videos = []

        comments = []
        for vid_id in tt_videos:
            comments.extend(get_comments(vid_id, limit=20))
        return comments
    except Exception as e:
        print(f"[ENGAGE][TT] Error: {e}")
        return []


def _collect_youtube_interactions() -> list:
    """Recolecta comentarios de YouTube."""
    try:
        from publishers.youtube import get_video_comments, is_configured
        if not is_configured():
            print("[ENGAGE][YT] No configurado — skipping")
            return []

        log_path = f"{DATA_DIR}/published_log.json"
        try:
            with open(log_path) as f:
                log = json.load(f)
            yt_videos = [
                e["post_id"] for e in log
                if e.get("canal") == "youtube" and e.get("post_id")
            ][-5:]
        except Exception:
            yt_videos = []

        comments = []
        for vid_id in yt_videos:
            comments.extend(get_video_comments(vid_id, limit=20))
        return comments
    except Exception as e:
        print(f"[ENGAGE][YT] Error: {e}")
        return []


def _collect_linkedin_interactions() -> list:
    """Recolecta comentarios de posts recientes de LinkedIn."""
    try:
        from publishers.linkedin import get_post_comments, is_configured
        if not is_configured():
            print("[ENGAGE][LI] No configurado — skipping")
            return []

        log_path = f"{DATA_DIR}/published_log.json"
        try:
            with open(log_path) as f:
                log = json.load(f)
            li_posts = [
                e["post_id"] for e in log
                if e.get("canal") == "linkedin" and e.get("post_id")
            ][-5:]
        except Exception:
            li_posts = []

        comments = []
        for post_id in li_posts:
            comments.extend(get_post_comments(post_id))
        return comments
    except Exception as e:
        print(f"[ENGAGE][LI] Error: {e}")
        return []


def run() -> list:
    """
    Ejecuta el ciclo completo de engagement:
    1. Recolecta de los 5 canales
    2. Filtra ya procesados
    3. Clasifica con Claude
    4. Retorna lista de interacciones enriquecidas
    """
    print("\n[ENGAGE] Iniciando recolección de interacciones...")
    seen = _load_seen()

    all_raw = []
    all_raw.extend(_collect_facebook_interactions())
    all_raw.extend(_collect_instagram_interactions())
    all_raw.extend(_collect_tiktok_interactions())
    all_raw.extend(_collect_youtube_interactions())
    all_raw.extend(_collect_linkedin_interactions())

    # Filtrar ya procesados
    new_interactions = [
        i for i in all_raw
        if i.get("interaction_id") not in seen
    ]
    print(f"[ENGAGE] {len(new_interactions)} nuevas interacciones a clasificar")

    classified = []
    for interaction in new_interactions:
        # Omitir si texto está vacío
        texto = interaction.get("texto", "").strip()
        if not texto or len(texto) < 3:
            _mark_seen(interaction["interaction_id"])
            continue

        try:
            classification = classify_interaction(
                texto=texto,
                usuario=interaction.get("usuario", "unknown"),
                canal=interaction.get("canal", ""),
                tipo=interaction.get("tipo", "comment")
            )

            enriched = {**interaction, **classification}

            # Agregar alerta de ventana de Messenger si aplica
            if interaction.get("alerta_ventana"):
                enriched["alerta"] = "⚠ VENTANA 24H CERRANDO"

            classified.append(enriched)
            _mark_seen(interaction["interaction_id"])
            print(
                f"[ENGAGE] {interaction['canal'].upper()} | "
                f"@{interaction.get('usuario', '?')} | "
                f"{classification.get('intencion', '?')} | "
                f"score: {classification.get('score_lead', '-')}"
            )

        except Exception as e:
            print(f"[ENGAGE] Error clasificando {interaction.get('interaction_id')}: {e}")

    # Guardar en archivo para otros agentes
    with open(INTERACTIONS_FILE, "w") as f:
        json.dump(classified, f, indent=2, ensure_ascii=False)

    # Estadísticas
    leads = [i for i in classified if i.get("requiere_registro_lead")]
    replies_needed = [i for i in classified if i.get("requiere_respuesta")]
    print(f"\n[ENGAGE] Resultado: {len(classified)} clasificadas | "
          f"{len(leads)} leads | {len(replies_needed)} requieren respuesta")

    return classified
