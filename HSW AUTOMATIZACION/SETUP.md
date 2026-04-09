# Nexus IQ Agent — Guía de Setup Completa

## Stack
- Python 3.11+
- Claude Sonnet (Anthropic API)
- Meta Graph API v21 (Facebook + Instagram)
- TikTok Content Posting API
- YouTube Data API v3
- LinkedIn UGC Posts API
- Google Sheets API (CRM)

---

## 1. Instalación

```bash
cd nexus-agent
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.template .env
```

---

## 2. Tokens requeridos — dónde conseguir cada uno

### ANTHROPIC (disponible inmediato)
1. Ir a https://console.anthropic.com
2. API Keys → Create Key
3. Copiar en `.env` como `ANTHROPIC_API_KEY`

### LINKEDIN (disponible inmediato — ya tenés el token)
1. Tu token actual de 60 días funciona
2. Para renovar: https://www.linkedin.com/developers/apps
3. Tu app → Auth → OAuth 2.0 tokens

### GOOGLE SHEETS — Service Account
1. https://console.cloud.google.com
2. Crear proyecto "nexus-iq-agent"
3. Habilitar: Google Sheets API + Google Drive API
4. IAM & Admin → Service Accounts → Create
5. Descargar JSON → guardar como `credentials/gsa.json`
6. Crear Spreadsheet en Google Sheets
7. Compartir el Spreadsheet con el email del Service Account
8. Copiar el ID del Spreadsheet (en la URL) → `SHEETS_SPREADSHEET_ID`

### YOUTUBE — OAuth2
1. https://console.cloud.google.com (mismo proyecto)
2. Habilitar: YouTube Data API v3
3. Credentials → Create → OAuth 2.0 Client ID (Desktop App)
4. Descargar el JSON de credenciales
5. Correr una vez para obtener refresh_token:
```bash
python scripts/get_youtube_token.py
```
6. Copiar `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`

### META — Facebook + Instagram (pendiente App Review)
1. https://developers.facebook.com → My Apps → Create App
2. Tipo: Business
3. Agregar producto: Facebook Login + Instagram Graph API
4. Permisos a solicitar en App Review:
   - pages_manage_posts
   - pages_read_engagement
   - pages_manage_engagement
   - instagram_content_publish
   - instagram_manage_comments
   - pages_messaging
5. Mientras el review llega → usar Graph API Explorer para token temporal:
   https://developers.facebook.com/tools/explorer
6. Seleccionar tu App → tu Page → Generate Access Token
7. Extender a 60 días: https://developers.facebook.com/tools/debug/accesstoken

### TIKTOK (pendiente Developer Portal)
1. https://developers.tiktok.com
2. Manage Apps → Create App
3. Producto: Content Posting API
4. Completar formulario de solicitud (1-3 semanas de aprobación)
5. Una vez aprobado, OAuth flow para obtener access + refresh token

---

## 3. Comandos de operación

```bash
# Ver estado del sistema
python nexus_orchestrator.py --mode status

# Ciclo completo (fetch noticias + leer interacciones)
python nexus_orchestrator.py --mode full

# Solo noticias y contenido
python nexus_orchestrator.py --mode content

# Solo interacciones, leads y respuestas
python nexus_orchestrator.py --mode engage

# Modo prueba — nada se publica
python nexus_orchestrator.py --mode full --dry-run

# Aprobar cola de contenido y respuestas
python approval_cli.py

# Ver solo contenido pendiente
python approval_cli.py --content

# Ver solo respuestas pendientes
python approval_cli.py --replies

# Ver leads de hoy
python approval_cli.py --leads

# Ver todos los leads nuevos
python approval_cli.py --leads all
```

---

## 4. Orden de activación recomendado

| Semana | Acción |
|--------|--------|
| 1 | Instalar, configurar Anthropic + Sheets + LinkedIn. Probar con `--dry-run`. |
| 1 | Correr `--mode content` y aprobar primeros posts de LinkedIn. |
| 2 | Configurar YouTube OAuth. Activar publicación de Shorts. |
| 2 | Tramitar Meta App + App Review (proceso paralelo). |
| 3 | Tramitar TikTok Developer Portal (proceso paralelo). |
| 4+ | Activar Meta (FB + IG) cuando llegue el App Review. |
| 4+ | Activar TikTok cuando llegue la aprobación. |

---

## 5. Estructura de archivos de datos

```
data/
├── seen_items.json       # URLs e IDs ya procesados (deduplicación)
├── queue.json            # Contenido pendiente de aprobación
├── pending_replies.json  # Respuestas pendientes de aprobación
├── interactions.json     # Última ejecución de engagement_agent
└── events.log            # Audit trail completo
```

---

## 6. Notas importantes

**Meta — ventana de 24h en Messenger:**
Solo podés responder mensajes de Messenger dentro de las 24 horas del último
mensaje del usuario. El CLI muestra "⚠ VENTANA CERRANDO" cuando quedan
menos de 4 horas. Priorizá esas aprobaciones.

**TikTok — tokens de 24h:**
El access token de TikTok expira cada 24 horas. El sistema lo renueva
automáticamente usando el refresh token. Si falla, corré manualmente:
```bash
python scripts/refresh_tiktok_token.py
```

**Instagram — requiere media URL:**
Para publicar en Instagram necesitás una URL pública de imagen/video.
El agente genera el texto (caption/script) pero el asset visual
lo tenés que producir vos y subir a un hosting público (puede ser
tu propio servidor, Cloudinary, o similar).

**YouTube — privacidad:**
Los videos se suben como `private` por defecto. Los podés hacer públicos
desde YouTube Studio después de revisarlos, o cambiar `privacy="public"`
en el código una vez que estés cómodo con el flujo.
