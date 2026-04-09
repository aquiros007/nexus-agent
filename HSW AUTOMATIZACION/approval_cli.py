"""
approval_cli.py
Interfaz de control de Abel — aprobación 1-click de contenido y respuestas.
Corre desde Claude Code: python approval_cli.py

Comandos:
  python approval_cli.py              → cola completa (contenido + respuestas)
  python approval_cli.py --leads      → ver leads de hoy
  python approval_cli.py --leads all  → todos los leads nuevos
  python approval_cli.py --content    → solo contenido pendiente
  python approval_cli.py --replies    → solo respuestas pendientes
"""
import argparse
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Colores ANSI para terminal ──────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
PURPLE = "\033[38;5;99m"
TEAL   = "\033[38;5;73m"
AMBER  = "\033[38;5;214m"
RED    = "\033[38;5;203m"
GREEN  = "\033[38;5;114m"
BLUE   = "\033[38;5;111m"
CORAL  = "\033[38;5;209m"
GRAY   = "\033[38;5;245m"

CANAL_COLORS = {
    "facebook":  BLUE,
    "instagram": CORAL,
    "tiktok":    RED,
    "youtube":   RED,
    "linkedin":  TEAL,
}

INTENCION_COLORS = {
    "lead_caliente":    f"{BOLD}{RED}",
    "lead_tibio":       AMBER,
    "fan":              GREEN,
    "pregunta_general": TEAL,
    "troll":            GRAY,
    "spam":             GRAY,
}


def _header():
    dry = os.getenv("DRY_RUN", "false").lower() == "true"
    dry_tag = f" {AMBER}[DRY-RUN]{RESET}" if dry else ""
    print(f"\n{PURPLE}{BOLD}{'═'*58}{RESET}")
    print(f"{PURPLE}{BOLD}  NEXUS IQ AGENT — APPROVAL QUEUE{RESET}{dry_tag}")
    print(f"{PURPLE}{BOLD}  {datetime.now().strftime('%d %b %Y  %H:%M')}{RESET}")
    print(f"{PURPLE}{BOLD}{'═'*58}{RESET}\n")


def _canal_tag(canal: str) -> str:
    color = CANAL_COLORS.get(canal, GRAY)
    return f"{color}[{canal.upper()}]{RESET}"


def _score_color(score: int) -> str:
    if score >= 80:
        return f"{BOLD}{GREEN}{score}{RESET}"
    if score >= 60:
        return f"{AMBER}{score}{RESET}"
    return f"{GRAY}{score}{RESET}"


def _intencion_tag(intencion: str) -> str:
    color = INTENCION_COLORS.get(intencion, GRAY)
    return f"{color}{intencion.upper()}{RESET}"


def _prompt_action(options: str = "[A]probar  [E]ditar  [S]kip  [Q]uit") -> str:
    print(f"\n  {DIM}{options}{RESET}")
    try:
        choice = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n\nSaliendo...")
        sys.exit(0)
    return choice


def _edit_text(current: str) -> str:
    """Permite editar un draft directamente en terminal."""
    print(f"\n{AMBER}── EDITOR ── (pega el texto nuevo y presiona Enter dos veces){RESET}")
    print(f"{DIM}Actual:{RESET}\n{current}\n")
    print(f"{AMBER}Nuevo texto (Enter vacío = mantener actual):{RESET}")
    lines = []
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            break
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    new_text = "\n".join(lines[:-1] if lines else []).strip()
    return new_text if new_text else current


# ─────────────────────────────────────────────────────────────────────────
# SECCIÓN: CONTENIDO
# ─────────────────────────────────────────────────────────────────────────

def review_content():
    """Muestra y procesa cola de contenido pendiente."""
    from agents.content_agent import get_pending, mark_approved
    from agents.publisher_agent import publish_content

    pending = get_pending()

    if not pending:
        print(f"  {GREEN}✓ Sin contenido pendiente{RESET}\n")
        return

    print(f"{BOLD}  CONTENIDO PENDIENTE: {len(pending)} items{RESET}\n")

    for i, item in enumerate(pending, 1):
        print(f"{PURPLE}{'─'*58}{RESET}")
        print(f"  {BOLD}[{i}/{len(pending)}] CONTENIDO{RESET}  "
              f"Score: {_score_color(item.get('score', 0))}  "
              f"{AMBER}{item.get('prioridad', '').upper()}{RESET}")
        print(f"\n  {BOLD}{item.get('title', '')}{RESET}")
        print(f"  {DIM}Fuente: {item.get('source', '')}  |  "
              f"Pillar: {item.get('pillar', '')}  |  "
              f"LATAM: {item.get('relevancia_latam', '')}{RESET}")
        print(f"  {DIM}Ángulo: {item.get('angulo', '')}{RESET}\n")

        # Mostrar drafts por canal
        drafts = item.get("drafts", {})
        canales_disponibles = [c for c, d in drafts.items() if d.get("draft")]

        print(f"  {BOLD}Drafts generados:{RESET}")
        for canal in canales_disponibles:
            draft_text = drafts[canal].get("draft", "")
            preview = draft_text[:120].replace("\n", " ")
            print(f"    {_canal_tag(canal)} {DIM}{preview}...{RESET}")

        print(f"\n  {DIM}URL: {item.get('url', '')}{RESET}")

        # Acción
        choice = _prompt_action(
            "[A]probar todos  [S]eleccionar canales  [E]ditar  [K]skip  [Q]uit"
        )

        if choice == "q":
            print("\nSaliendo...\n")
            sys.exit(0)

        elif choice == "k" or choice == "s" and not choice:
            print(f"  {GRAY}Skipped{RESET}")
            continue

        elif choice == "s":
            # Seleccionar canales específicos
            print(f"\n  Canales disponibles: {', '.join(canales_disponibles)}")
            print(f"  {DIM}Ingresá los canales separados por coma (ej: linkedin,instagram):{RESET}")
            try:
                selected_input = input("  > ").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            selected = [c.strip() for c in selected_input.split(",")
                        if c.strip() in canales_disponibles]
            if not selected:
                print(f"  {RED}Ningún canal válido seleccionado{RESET}")
                continue
            approved_item = mark_approved(item["item_id"], channels=selected)
            _execute_publish_content(approved_item)

        elif choice == "e":
            # Editar canal específico
            print(f"\n  ¿Qué canal querés editar? ({'/'.join(canales_disponibles)})")
            try:
                canal_edit = input("  > ").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            if canal_edit in drafts:
                new_text = _edit_text(drafts[canal_edit].get("draft", ""))
                item["drafts"][canal_edit]["draft"] = new_text
                # Guardar edición en queue
                from agents.content_agent import _load_queue, _save_queue
                queue = _load_queue()
                for q in queue:
                    if q.get("item_id") == item["item_id"]:
                        q["drafts"][canal_edit]["draft"] = new_text
                _save_queue(queue)
                print(f"  {GREEN}✓ Draft de {canal_edit} actualizado{RESET}")
            # Volver a mostrar para aprobar
            choice = _prompt_action("[A]probar ahora  [S]kip")
            if choice != "a":
                continue
            approved_item = mark_approved(item["item_id"])
            _execute_publish_content(approved_item)

        elif choice == "a":
            approved_item = mark_approved(item["item_id"])
            _execute_publish_content(approved_item)

        else:
            print(f"  {GRAY}Opción no reconocida — skipped{RESET}")


def _execute_publish_content(item: dict):
    """Ejecuta la publicación de un item aprobado."""
    from agents.publisher_agent import publish_content
    if not item:
        print(f"  {RED}Error: item no encontrado{RESET}")
        return
    print(f"\n  {TEAL}Publicando en {item.get('approved_channels', [])}...{RESET}")
    results = publish_content(item)
    for canal, result in results.items():
        if "error" in result:
            print(f"  {_canal_tag(canal)} {RED}✗ {result['error']}{RESET}")
        else:
            post_id = result.get("id", result.get("publish_id", "ok"))
            print(f"  {_canal_tag(canal)} {GREEN}✓ Publicado: {post_id}{RESET}")


# ─────────────────────────────────────────────────────────────────────────
# SECCIÓN: RESPUESTAS
# ─────────────────────────────────────────────────────────────────────────

def review_replies():
    """Muestra y procesa cola de respuestas pendientes."""
    from agents.responder_agent import get_pending, mark_approved
    from agents.publisher_agent import publish_reply

    pending = get_pending()

    if not pending:
        print(f"  {GREEN}✓ Sin respuestas pendientes{RESET}\n")
        return

    print(f"{BOLD}  RESPUESTAS PENDIENTES: {len(pending)}{RESET}\n")

    for i, reply in enumerate(pending, 1):
        print(f"{BLUE}{'─'*58}{RESET}")

        # Alerta ventana 24h Messenger
        if reply.get("alerta"):
            print(f"  {RED}{BOLD}{reply['alerta']}{RESET}")

        print(f"  {BOLD}[{i}/{len(pending)}] RESPUESTA{RESET}  "
              f"{_canal_tag(reply.get('canal', ''))}  "
              f"tipo: {DIM}{reply.get('tipo', '')}{RESET}  "
              f"{_intencion_tag(reply.get('intencion', ''))}")

        print(f"\n  {BOLD}@{reply.get('usuario', '')}{RESET}  "
              f"{DIM}{reply.get('created_at', '')[:16]}{RESET}")

        print(f"\n  {DIM}Original:{RESET}")
        print(f"  {GRAY}\"{reply.get('mensaje_original', '')[:200]}\"{RESET}")

        print(f"\n  {BOLD}Draft:{RESET}")
        print(f"  {reply.get('draft', '')}")

        tono = reply.get("tono", "")
        cta = reply.get("incluye_cta", False)
        chars = reply.get("chars", 0)
        print(f"\n  {DIM}Tono: {tono}  |  CTA: {'Sí' if cta else 'No'}  |  {chars} chars{RESET}")

        if reply.get("lead_id"):
            print(f"  {AMBER}Lead registrado: {reply['lead_id']}{RESET}")

        choice = _prompt_action("[A]probar  [E]ditar  [S]kip  [Q]uit")

        if choice == "q":
            print("\nSaliendo...\n")
            sys.exit(0)

        elif choice == "s":
            print(f"  {GRAY}Skipped{RESET}")
            continue

        elif choice == "e":
            new_text = _edit_text(reply.get("draft", ""))
            reply["draft"] = new_text
            # Guardar edición
            from agents.responder_agent import _load_pending, _save_pending
            pending_all = _load_pending()
            for p in pending_all:
                if p.get("reply_id") == reply.get("reply_id"):
                    p["draft"] = new_text
            _save_pending(pending_all)
            print(f"  {GREEN}✓ Draft actualizado{RESET}")
            choice = _prompt_action("[A]probar ahora  [S]kip")
            if choice != "a":
                continue
            _execute_publish_reply(reply)

        elif choice == "a":
            approved = mark_approved(reply.get("reply_id"))
            if approved:
                _execute_publish_reply(approved)

        else:
            print(f"  {GRAY}Opción no reconocida — skipped{RESET}")


def _execute_publish_reply(reply: dict):
    """Ejecuta la publicación de un reply aprobado."""
    from agents.publisher_agent import publish_reply
    print(f"\n  {TEAL}Publicando reply en {reply.get('canal', '')}...{RESET}")
    result = publish_reply(reply)
    if "error" in result:
        print(f"  {RED}✗ Error: {result['error']}{RESET}")
    else:
        print(f"  {GREEN}✓ Reply publicado{RESET}")


# ─────────────────────────────────────────────────────────────────────────
# SECCIÓN: LEADS
# ─────────────────────────────────────────────────────────────────────────

def show_leads(scope: str = "today"):
    """Muestra leads del CRM."""
    try:
        if scope == "today":
            from integrations.sheets_client import get_leads_today
            leads = get_leads_today()
            title = "LEADS DE HOY"
        else:
            from integrations.sheets_client import get_leads_by_status
            leads = get_leads_by_status("Nuevo")
            title = "LEADS NUEVOS (todos)"
    except Exception as e:
        print(f"  {RED}Error conectando con Google Sheets: {e}{RESET}")
        print(f"  {DIM}Verificá que GOOGLE_SERVICE_ACCOUNT_JSON esté configurado{RESET}")
        return

    if not leads:
        print(f"  {GREEN}✓ Sin leads en esta categoría{RESET}\n")
        return

    print(f"{BOLD}  {title}: {len(leads)}{RESET}\n")
    print(f"  {'ID':<18} {'Canal':<12} {'Usuario':<20} {'Intención':<15} {'Score':>5}  Estado")
    print(f"  {'─'*85}")

    for lead in leads:
        canal = lead.get("Canal Origen", "")
        color = CANAL_COLORS.get(canal, GRAY)
        intencion = lead.get("Intención", "")
        int_color = INTENCION_COLORS.get(intencion, GRAY)
        score = lead.get("Score Lead", 0)

        print(
            f"  {DIM}{lead.get('ID', ''):<18}{RESET} "
            f"{color}{canal:<12}{RESET} "
            f"{lead.get('Nombre / Handle', ''):<20} "
            f"{int_color}{intencion:<15}{RESET} "
            f"{_score_color(int(score) if str(score).isdigit() else 0):>5}  "
            f"{lead.get('Estado', '')}"
        )

    print(f"\n  {DIM}Abrí Google Sheets para ver detalles completos{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────
# SECCIÓN: SUMMARY
# ─────────────────────────────────────────────────────────────────────────

def show_summary():
    """Muestra resumen rápido del estado del sistema."""
    try:
        from agents.content_agent import get_pending as cp
        from agents.responder_agent import get_pending as rp
        content_count = len(cp())
        reply_count = len(rp())
    except Exception:
        content_count = reply_count = "?"

    try:
        from integrations.sheets_client import get_leads_today
        leads_today = len(get_leads_today())
    except Exception:
        leads_today = "?"

    print(f"  {'─'*40}")
    print(f"  {BOLD}Contenido pendiente:{RESET}  {PURPLE}{content_count}{RESET}")
    print(f"  {BOLD}Respuestas pendientes:{RESET} {BLUE}{reply_count}{RESET}")
    print(f"  {BOLD}Leads hoy:{RESET}            {AMBER}{leads_today}{RESET}")
    print(f"  {'─'*40}")
    print(f"  {DIM}DRY_RUN: {os.getenv('DRY_RUN', 'false')}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nexus IQ — Approval CLI")
    parser.add_argument("--content",  action="store_true", help="Solo contenido pendiente")
    parser.add_argument("--replies",  action="store_true", help="Solo respuestas pendientes")
    parser.add_argument("--leads",    nargs="?", const="today",
                        metavar="today|all", help="Ver leads (default: today)")
    parser.add_argument("--dry-run",  action="store_true", help="No publica nada")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    _header()
    show_summary()

    if args.leads is not None:
        show_leads(scope=args.leads)
        return

    if args.content:
        review_content()
        return

    if args.replies:
        review_replies()
        return

    # Cola completa por defecto
    review_content()
    print()
    review_replies()
    print()

    # Preguntar si ver leads
    print(f"  {DIM}¿Ver leads de hoy? [s/N]{RESET}")
    try:
        if input("  > ").strip().lower() == "s":
            print()
            show_leads("today")
    except (KeyboardInterrupt, EOFError):
        pass

    print(f"\n{GREEN}  ✓ Cola procesada — hasta la próxima{RESET}\n")


if __name__ == "__main__":
    main()
