"""
agents/content_agent.py
Fetch RSS de fuentes LLM → scoring → draft de contenido x5 canales.
"""
import json
import os
import feedparser
from datetime import datetime, timezone, timedelta
from integrations.claude_client import score_news_item, generate_content_for_channel
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "./data"
QUEUE_FILE = f"{DATA_DIR}/queue.json"
SEEN_FILE  = f"{DATA_DIR}/seen_items.json"

RSS_FEEDS = [
    {"name": "Anthropic",  "url": "https://www.anthropic.com/news/rss.xml"},
    {"name": "OpenAI",     "url": "https://openai.com/news/rss"},
    {"name": "Google AI",  "url": "https://blog.google/technology/ai/rss/"},
    {"name": "Mistral",    "url": "https://mistral.ai/news/rss"},
    {"name": "DeepMind",   "url": "https://deepmind.google/discover/blog/rss/"},
]

CHANNELS = ["facebook", "instagram", "tiktok", "youtube", "linkedin"]
SCORE_THRESHOLD = 60   # Score mínimo para generar contenido
HOURS_LOOKBACK  = 72   # Horas hacia atrás para buscar noticias


def _load_seen() -> set:
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
            return set(i for i in data if not i.startswith("interaction_"))
    except Exception:
        return set()


def _mark_seen(item_url: str):
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
    except Exception:
        data = []
    if item_url not in data:
        data.append(item_url)
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f)


def _load_queue() -> list:
    try:
        with open(QUEUE_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def fetch_feeds() -> list:
    """Parsea todos los RSS feeds y retorna items nuevos."""
    seen = _load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)
    items = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                url = entry.get("link", "")
                if url in seen:
                    continue

                # Verificar fecha
                published = entry.get("published_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue

                summary = (
                    entry.get("summary", "")
                    or entry.get("description", "")
                )[:500]

                items.append({
                    "url": url,
                    "title": entry.get("title", ""),
                    "summary": summary,
                    "source": feed_info["name"],
                    "published": entry.get("published", "")
                })

            print(f"[CONTENT] {feed_info['name']}: {len(feed.entries)} entradas")
        except Exception as e:
            print(f"[CONTENT] Error leyendo {feed_info['name']}: {e}")

    print(f"[CONTENT] {len(items)} items nuevos encontrados")
    return items


def run() -> list:
    """
    Ciclo completo de contenido:
    1. Fetch RSS
    2. Score cada item con Claude
    3. Para items con score >= threshold: generar drafts x5 canales
    4. Encolar en queue.json para aprobación
    """
    print("\n[CONTENT] Iniciando ciclo de contenido...")
    raw_items = fetch_feeds()

    if not raw_items:
        print("[CONTENT] No hay items nuevos")
        return []

    queue = _load_queue()
    existing_urls = {q.get("url") for q in queue}
    added = []

    for item in raw_items:
        if item["url"] in existing_urls:
            _mark_seen(item["url"])
            continue

        try:
            # Score con Claude
            evaluation = score_news_item(
                title=item["title"],
                summary=item["summary"],
                source=item["source"]
            )

            score = evaluation.get("score", 0)
            prioridad = evaluation.get("prioridad", "skip")

            print(
                f"[CONTENT] Score {score:3d} | {prioridad:8s} | "
                f"{item['source']:10s} | {item['title'][:55]}"
            )

            if score < SCORE_THRESHOLD or prioridad == "skip":
                _mark_seen(item["url"])
                continue

            # Generar drafts para cada canal
            drafts = {}
            angulo = evaluation.get("angulo", item["title"])

            for channel in CHANNELS:
                try:
                    draft = generate_content_for_channel(
                        title=item["title"],
                        summary=item["summary"],
                        angulo=angulo,
                        channel=channel
                    )
                    drafts[channel] = draft
                except Exception as e:
                    print(f"[CONTENT] Error generando draft {channel}: {e}")
                    drafts[channel] = {"canal": channel, "draft": "", "notas": str(e)}

            queue_entry = {
                "item_id": f"content_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "url": item["url"],
                "title": item["title"],
                "source": item["source"],
                "published": item["published"],
                "score": score,
                "prioridad": prioridad,
                "pillar": evaluation.get("pillar", ""),
                "angulo": angulo,
                "relevancia_latam": evaluation.get("relevancia_latam", ""),
                "drafts": drafts,
                "estado": "pending_approval",
                "created_at": datetime.now().isoformat()
            }

            queue.append(queue_entry)
            added.append(queue_entry)
            _mark_seen(item["url"])
            existing_urls.add(item["url"])

        except Exception as e:
            print(f"[CONTENT] Error procesando '{item['title'][:40]}': {e}")

    _save_queue(queue)
    print(f"\n[CONTENT] {len(added)} items nuevos en cola de aprobación")
    return added


def get_pending() -> list:
    """Retorna items pendientes de aprobación."""
    queue = _load_queue()
    return [q for q in queue if q.get("estado") == "pending_approval"]


def mark_approved(item_id: str, channels: list = None) -> dict:
    """Marca item como aprobado para canales específicos."""
    queue = _load_queue()
    for item in queue:
        if item.get("item_id") == item_id:
            item["estado"] = "approved"
            item["approved_channels"] = channels or CHANNELS
            item["approved_at"] = datetime.now().isoformat()
            _save_queue(queue)
            return item
    return {}


def mark_published(item_id: str, canal: str, post_id: str):
    """Registra publicación exitosa."""
    queue = _load_queue()
    for item in queue:
        if item.get("item_id") == item_id:
            if "published_to" not in item:
                item["published_to"] = {}
            item["published_to"][canal] = {
                "post_id": post_id,
                "published_at": datetime.now().isoformat()
            }
            all_done = all(
                canal in item.get("published_to", {})
                for canal in item.get("approved_channels", [])
            )
            if all_done:
                item["estado"] = "published"
    _save_queue(queue)
