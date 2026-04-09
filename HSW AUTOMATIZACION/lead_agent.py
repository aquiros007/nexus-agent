"""
agents/lead_agent.py
Toma interacciones clasificadas como leads, enriquece perfiles,
y los registra en Google Sheets CRM.
"""
import json
import os
from integrations.claude_client import enrich_lead_profile
from integrations.sheets_client import register_lead
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "./data"


def run(interactions: list) -> list:
    """
    Procesa interacciones que son leads.
    Retorna lista de leads registrados con sus IDs de Sheets.
    """
    leads_to_process = [
        i for i in interactions
        if i.get("requiere_registro_lead")
        and i.get("intencion") in ("lead_caliente", "lead_tibio")
    ]

    print(f"\n[LEAD] {len(leads_to_process)} leads a registrar en Sheets")
    registered = []

    for interaction in leads_to_process:
        try:
            # Enriquecer perfil con Claude
            profile = enrich_lead_profile(
                usuario=interaction.get("usuario", ""),
                canal=interaction.get("canal", ""),
                mensaje=interaction.get("texto", ""),
                bio_publica=interaction.get("bio_publica", "")
            )

            # Registrar en Google Sheets
            lead_id = register_lead(
                usuario=interaction.get("usuario", ""),
                canal=interaction.get("canal", ""),
                tipo=interaction.get("tipo", ""),
                mensaje=interaction.get("texto", ""),
                intencion=interaction.get("intencion", ""),
                score=interaction.get("score_lead", 0),
                profile=profile,
                url=interaction.get("url", "")
            )

            interaction["lead_id"] = lead_id
            interaction["profile"] = profile
            registered.append(interaction)

        except Exception as e:
            print(f"[LEAD] Error registrando lead {interaction.get('interaction_id')}: {e}")

    print(f"[LEAD] {len(registered)} leads registrados")
    return registered
