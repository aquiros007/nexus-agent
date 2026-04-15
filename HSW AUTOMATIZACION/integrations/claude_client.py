"""
integrations/claude_client.py
Wrapper único para Claude API — Nexus IQ Agent
Todas las llamadas al modelo pasan por aquí.
"""
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

NEXUS_SYSTEM_PROMPT = """Eres el agente editorial de Nexus IQ Strategies LLC, 
firma de consultoría de IA para C-suite en Centroamérica, liderada por Abel Quirós Quirós.

VOZ DE MARCA (Brand Voice Nexus IQ v5.1):
- Ejecutivo con resultados reales. Directo y preciso.
- Anclado en datos verificables. Voz LATAM con contexto global.
- Ejes: Gobernanza + Revenue con IA. Human in the Loop como posición real.
- NO sos: académico abstracto, hype-driven, fabricador de cifras.
- NUNCA uses: "disruptivo", "transformacional", "holístico", "revolucionario".
- CTA WhatsApp siempre: https://wa.me/message/6Q5VSRREEPF2P1

REGLAS IRROMPIBLES:
- Nunca inventes datos, estadísticas o casos.
- Siempre primera persona desde la perspectiva de Abel.
- Máximo 5 puntos en listas.
- Hashtags: máx 5, siempre incluye #NexusIQ."""


def ask(prompt: str, system: str = None, max_tokens: int = 1500) -> str:
    """Llamada simple a Claude. Retorna texto plano."""
    response = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=max_tokens,
        system=system or NEXUS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def ask_json(prompt: str, system: str = None, max_tokens: int = 1500) -> dict:
    """Llamada a Claude que retorna JSON parseado."""
    import json

    json_system = (system or NEXUS_SYSTEM_PROMPT) + \
        "\n\nRESPONDE ÚNICAMENTE CON JSON VÁLIDO. Sin texto adicional, sin markdown, sin backticks."

    raw = ask(prompt, system=json_system, max_tokens=max_tokens)

    # Limpiar posibles backticks si Claude los incluye
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw)


def score_news_item(title: str, summary: str, source: str) -> dict:
    """
    Evalúa relevancia de una noticia para Nexus IQ.
    Retorna: {score, relevancia_latam, angulo, prioridad}
    """
    prompt = f"""Evalúa esta noticia de IA para Nexus IQ Strategies.

NOTICIA:
Título: {title}
Fuente: {source}
Resumen: {summary}

Retorna JSON con exactamente estas claves:
{{
  "score": <número 0-100>,
  "relevancia_latam": <"alta"|"media"|"baja">,
  "angulo": <string: ángulo editorial para C-suite LATAM, máx 20 palabras>,
  "prioridad": <"breaking"|"evergreen"|"skip">,
  "pillar": <"gobernanza"|"revenue"|"herramientas"|"latam"|"casos_reales">
}}

Criterios de score alto (>70):
- Impacto directo en decisiones empresariales C-suite
- Relevante para Centroamérica/LATAM
- Relacionado con gobernanza IA, revenue, automatización ejecutiva
- Noticia de últimas 48 horas de fuente primaria (Anthropic, OpenAI, Google, Mistral)"""

    return ask_json(prompt)


def generate_content_for_channel(
    title: str,
    summary: str,
    angulo: str,
    channel: str
) -> dict:
    """
    Genera borrador de contenido para un canal específico.
    channel: 'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'linkedin'
    """
    specs = {
        "facebook": "Post de texto para Facebook Page de Nexus IQ. Máx 500 palabras. Tono ejecutivo-cercano. Incluye pregunta de cierre para generar comentarios. CTA al WhatsApp.",
        "instagram": "Caption para Instagram. Máx 2200 chars pero óptimo 150-300. Hook en primera línea (antes del 'ver más'). Máx 5 hashtags incluyendo #NexusIQ. CTA WhatsApp al final.",
        "tiktok": "Script para TikTok de 45-60 segundos. Formato: [HOOK 3s] [DESARROLLO 40s] [CTA 5s]. Lenguaje dinámico pero profesional. Sin jerga juvenil. Dirígete a empresarios LATAM.",
        "youtube": "Descripción para YouTube Short (<60s). Incluye: párrafo introductorio (2-3 líneas), timestamps si aplica, CTA, hashtags SEO (#IA #InteligenciaArtificial #NexusIQ #LATAM).",
        "linkedin": "Post LinkedIn. Hook <200 chars antes del 'ver más'. Formato con → para listas. Perspectiva personal de Abel. Pregunta de cierre que genere debate real. CTA WhatsApp. Máx 5 hashtags."
    }

    channel_system = None
    if channel == "linkedin":
        channel_system = NEXUS_SYSTEM_PROMPT + """

INSTRUCCIONES ADICIONALES PARA LINKEDIN (linkedin-voice-publisher):
- Hook potente en <200 caracteres ANTES del "ver más" de LinkedIn. Debe generar curiosidad o tensión.
- Usa → para listas en lugar de bullets o números.
- Escribe en perspectiva personal de Abel Quirós, desde experiencia real y directa con clientes en LATAM.
- Incluye observaciones concretas ("He trabajado con...", "En los últimos meses vi que...") — nunca genéricas.
- Pregunta de cierre que genere debate real entre ejecutivos, no preguntas retóricas obvias.
- CTA al final: https://wa.me/message/6Q5VSRREEPF2P1
- Máximo 5 hashtags, siempre incluir #NexusIQ.
- NO uses emojis. NO uses formato bold (**texto**). Usa saltos de línea para respirar."""

    prompt = f"""Genera contenido para {channel.upper()} basado en esta noticia.

NOTICIA: {title}
RESUMEN: {summary}
ÁNGULO EDITORIAL: {angulo}

ESPECIFICACIONES PARA {channel.upper()}:
{specs[channel]}

Retorna JSON:
{{
  "canal": "{channel}",
  "draft": <string: el contenido completo listo para publicar>,
  "notas": <string: recomendaciones de producción si aplica, ej: "usar imagen de OpenAI blog">
}}"""

    return ask_json(prompt, system=channel_system)


def classify_interaction(
    texto: str,
    usuario: str,
    canal: str,
    tipo: str
) -> dict:
    """
    Clasifica intención de un comentario, DM o mensaje.
    Retorna intención, urgencia, si requiere respuesta y si es lead.
    """
    prompt = f"""Clasifica esta interacción en redes sociales de Nexus IQ Strategies.

CANAL: {canal}
TIPO: {tipo} (comment|dm|mention|reply|messenger)
USUARIO: {usuario}
MENSAJE: {texto}

Retorna JSON:
{{
  "intencion": <"lead_caliente"|"lead_tibio"|"fan"|"pregunta_general"|"troll"|"spam">,
  "urgencia": <"alta"|"media"|"baja">,
  "requiere_respuesta": <true|false>,
  "requiere_registro_lead": <true|false>,
  "score_lead": <número 0-100, solo si es lead>,
  "razon": <string: justificación breve de la clasificación, máx 15 palabras>
}}

Criterios lead_caliente (score >70): pregunta directa por servicios, precios, consultoría, menciona empresa o cargo, urgencia temporal.
Criterios lead_tibio (score 40-70): interés implícito, pide más información general, perfil ejecutivo visible.
Spam/troll: NUNCA registrar como lead, NO responder."""

    return ask_json(prompt)


def draft_reply(
    mensaje_original: str,
    usuario: str,
    canal: str,
    tipo: str,
    intencion: str,
    contexto_lead: dict = None
) -> dict:
    """
    Redacta respuesta personalizada con voz Nexus IQ.
    """
    contexto_str = ""
    if contexto_lead:
        contexto_str = f"\nCONTEXTO DEL LEAD: {contexto_lead}"

    prompt = f"""Redacta una respuesta para esta interacción en nombre de Nexus IQ / Abel Quirós.

CANAL: {canal} | TIPO: {tipo} | INTENCIÓN: {intencion}
USUARIO: {usuario}
MENSAJE ORIGINAL: {mensaje_original}
{contexto_str}

REGLAS DE RESPUESTA:
- Máx 3 párrafos cortos (o menos para comentarios)
- Tono: ejecutivo pero cercano, nunca robótico
- Si es lead_caliente: incluir CTA directo al WhatsApp
- Si es lead_tibio: valor primero, CTA suave al final
- Si es fan/pregunta_general: respuesta genuina, sin CTA forzado
- Para Messenger: respuesta más conversacional y cálida
- Para comentarios IG/FB: respuesta concisa (<150 chars idealmente)
- NUNCA mencionar que sos un agente de IA

Retorna JSON:
{{
  "draft": <string: respuesta lista para publicar>,
  "tono": <"ejecutivo_directo"|"ejecutivo_cercano"|"informativo"|"conversacional">,
  "incluye_cta": <true|false>,
  "chars": <número: longitud del draft>
}}"""

    return ask_json(prompt)


def enrich_lead_profile(
    usuario: str,
    canal: str,
    mensaje: str,
    bio_publica: str = ""
) -> dict:
    """
    Enriquece perfil del lead con datos inferidos.
    """
    prompt = f"""Construye el perfil de este lead para el CRM de Nexus IQ Strategies.

DATOS DISPONIBLES:
Usuario: {usuario}
Canal: {canal}
Mensaje: {mensaje}
Bio pública: {bio_publica or "No disponible"}

Infiere lo que puedas. Si no hay información suficiente, usa "No especificado".

Retorna JSON:
{{
  "nombre_display": <string: nombre o handle>,
  "cargo_inferido": <string o "No especificado">,
  "empresa_inferida": <string o "No especificado">,
  "pais_inferido": <string o "No especificado">,
  "industria_inferida": <string o "No especificado">,
  "necesidad_detectada": <string: qué problema o necesidad expresó, máx 20 palabras>,
  "siguiente_accion": <"llamada_discovery"|"enviar_info"|"nurturing"|"calificar_mas">
}}"""

    return ask_json(prompt)
