"""
nexus_orchestrator.py
Punto de entrada del sistema Nexus IQ Agent.
Coordina todos los subagentes sin acceder directamente a APIs.

Uso:
  python nexus_orchestrator.py --mode full
  python nexus_orchestrator.py --mode content
  python nexus_orchestrator.py --mode engage
  python nexus_orchestrator.py --mode full --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = "./data/events.log"


def _log(msg: str):
    """Escribe en log de eventos con timestamp."""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_content_cycle():
    """Ciclo de contenido: fetch → score → draft → encolar."""
    _log("=== INICIO CICLO CONTENT ===")
    from agents.content_agent import run
    items = run()
    _log(f"CONTENT: {len(items)} items encolados para aprobación")
    return items


def run_engagement_cycle():
    """Ciclo de engagement: leer → clasificar → leads → drafts reply."""
    _log("=== INICIO CICLO ENGAGEMENT ===")

    # 1. Leer y clasificar interacciones
    from agents.engagement_agent import run as engage_run
    interactions = engage_run()

    if not interactions:
        _log("ENGAGE: Sin interacciones nuevas")
        return

    # 2. Registrar leads
    leads = [i for i in interactions if i.get("requiere_registro_lead")]
    if leads:
        from agents.lead_agent import run as lead_run
        registered = lead_run(interactions)
        # Actualizar interactions con lead_ids asignados
        lead_map = {r["interaction_id"]: r for r in registered}
        for i in interactions:
            if i["interaction_id"] in lead_map:
                i["lead_id"] = lead_map[i["interaction_id"]].get("lead_id")
                i["profile"] = lead_map[i["interaction_id"]].get("profile")
        _log(f"LEAD: {len(registered)} leads registrados en Sheets")

    # 3. Generar drafts de respuesta
    replies_needed = [i for i in interactions if i.get("requiere_respuesta")]
    if replies_needed:
        from agents.responder_agent import run as responder_run
        drafts = responder_run(interactions)
        _log(f"RESPONDER: {len(drafts)} drafts encolados para aprobación")

    _log("=== FIN CICLO ENGAGEMENT ===")


def run_full_cycle():
    """Ciclo completo: contenido + engagement."""
    _log("=== INICIO CICLO COMPLETO ===")
    run_content_cycle()
    run_engagement_cycle()
    _log("=== FIN CICLO COMPLETO ===")


def print_status():
    """Muestra estado actual del sistema."""
    from agents.content_agent import get_pending as content_pending
    from agents.responder_agent import get_pending as reply_pending

    content_q = content_pending()
    reply_q = reply_pending()

    print("\n" + "="*50)
    print("  NEXUS IQ AGENT — STATUS")
    print("="*50)
    print(f"  Contenido pendiente aprobación: {len(content_q)}")
    print(f"  Respuestas pendientes aprobación: {len(reply_q)}")
    print(f"  DRY_RUN: {os.getenv('DRY_RUN', 'false')}")
    print("="*50)
    print("  Corré 'python approval_cli.py' para aprobar")
    print("="*50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Nexus IQ Agent Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["full", "content", "engage", "status"],
        default="status",
        help="Modo de ejecución"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sin publicar nada"
    )

    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
        print("[ORCHESTRATOR] Modo DRY-RUN activado")

    if args.mode == "full":
        run_full_cycle()
    elif args.mode == "content":
        run_content_cycle()
    elif args.mode == "engage":
        run_engagement_cycle()
    elif args.mode == "status":
        print_status()

    print_status()


if __name__ == "__main__":
    main()
