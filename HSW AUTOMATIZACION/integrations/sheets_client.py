"""
integrations/sheets_client.py
Google Sheets como CRM de leads — Nexus IQ Agent
Usa Service Account para autenticación sin intervención manual.
"""
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def _get_client():
    """Retorna cliente gspread autenticado via Service Account."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/gsa.json")
    creds = Credentials.from_service_account_file(sa_path, scopes=scopes)
    return gspread.authorize(creds)


def _get_sheet(sheet_name: str = "Leads"):
    """Retorna worksheet por nombre. Crea headers si está vacío."""
    client = _get_client()
    spreadsheet_id = os.getenv("SHEETS_SPREADSHEET_ID")
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        sheet = spreadsheet.worksheet(sheet_name)
    except Exception:
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

    # Verificar headers
    headers = sheet.row_values(1)
    if not headers:
        _init_headers(sheet)

    return sheet


def _init_headers(sheet):
    """Inicializa los headers del CRM."""
    headers = [
        "ID",
        "Fecha",
        "Nombre / Handle",
        "Canal Origen",
        "Tipo Interacción",
        "Mensaje Original",
        "Cargo Inferido",
        "Empresa Inferida",
        "País",
        "Industria",
        "Necesidad Detectada",
        "Intención",
        "Score Lead",
        "Estado",
        "Siguiente Acción",
        "Draft Respuesta",
        "Respuesta Enviada",
        "Fecha Respuesta",
        "Notas",
        "URL Interacción"
    ]
    sheet.update("A1", [headers])
    # Formato de headers (negrita)
    sheet.format("A1:T1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.5}
    })


def register_lead(
    usuario: str,
    canal: str,
    tipo: str,
    mensaje: str,
    intencion: str,
    score: int,
    profile: dict,
    draft_reply: str = "",
    url: str = ""
) -> str:
    """
    Registra un lead nuevo en Google Sheets.
    Retorna el ID asignado.
    Evita duplicados por usuario+canal.
    """
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    lead_id = f"NQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    row = [
        lead_id,
        fecha,
        profile.get("nombre_display", usuario),
        canal,
        tipo,
        mensaje[:500],  # Limitar longitud
        profile.get("cargo_inferido", ""),
        profile.get("empresa_inferida", ""),
        profile.get("pais_inferido", ""),
        profile.get("industria_inferida", ""),
        profile.get("necesidad_detectada", ""),
        intencion,
        score,
        "Nuevo",
        profile.get("siguiente_accion", ""),
        draft_reply[:1000] if draft_reply else "",
        "",   # Respuesta enviada (se llena luego)
        "",   # Fecha respuesta
        "",   # Notas manuales
        url
    ]

    if dry_run:
        print(f"[DRY-RUN] Lead que se registraría: {lead_id} — {usuario} ({canal})")
        return lead_id

    sheet = _get_sheet("Leads")

    # Verificar duplicado: mismo usuario + canal en últimas 24h
    existing = sheet.get_all_records()
    for record in existing:
        if (record.get("Nombre / Handle") == profile.get("nombre_display", usuario)
                and record.get("Canal Origen") == canal
                and record.get("Estado") == "Nuevo"):
            print(f"[SHEETS] Lead duplicado detectado — omitiendo: {usuario}")
            return record.get("ID", "DUPLICATE")

    sheet.append_row(row)
    print(f"[SHEETS] Lead registrado: {lead_id} — {usuario} ({canal}, score: {score})")
    return lead_id


def update_lead_status(lead_id: str, estado: str, notas: str = ""):
    """Actualiza el estado de un lead existente."""
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if dry_run:
        print(f"[DRY-RUN] Actualizaría lead {lead_id} → {estado}")
        return

    sheet = _get_sheet("Leads")
    records = sheet.get_all_records()

    for i, record in enumerate(records, start=2):  # fila 1 = headers
        if record.get("ID") == lead_id:
            sheet.update_cell(i, 14, estado)  # col N = Estado
            if notas:
                sheet.update_cell(i, 19, notas)  # col S = Notas
            if estado == "Contactado":
                sheet.update_cell(i, 17, "Sí")
                sheet.update_cell(i, 18, datetime.now().strftime("%Y-%m-%d %H:%M"))
            print(f"[SHEETS] Lead {lead_id} actualizado → {estado}")
            return

    print(f"[SHEETS] WARN: Lead {lead_id} no encontrado para actualizar")


def get_leads_today() -> list:
    """Retorna leads de hoy para el reporte del CLI."""
    sheet = _get_sheet("Leads")
    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    return [r for r in records if r.get("Fecha", "").startswith(today)]


def get_leads_by_status(estado: str = "Nuevo") -> list:
    """Retorna leads por estado."""
    sheet = _get_sheet("Leads")
    records = sheet.get_all_records()
    return [r for r in records if r.get("Estado") == estado]
