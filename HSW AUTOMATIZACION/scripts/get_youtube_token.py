"""
scripts/get_youtube_token.py
Flujo OAuth para obtener YouTube refresh token.

Uso:
  python scripts/get_youtube_token.py

Abre el browser, autorizás con tu cuenta de Google,
y el script guarda el refresh token en el .env automáticamente.
"""
import os
import sys
import json
import http.server
import threading
import webbrowser
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8090"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    """Captura el callback de OAuth."""
    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            OAuthHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>YouTube autorizado. Puedes cerrar esta ventana.</h2></body></html>"
            )
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())

    def log_message(self, format, *args):
        pass  # Silenciar logs del server


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: YOUTUBE_CLIENT_ID y YOUTUBE_CLIENT_SECRET deben estar en .env")
        sys.exit(1)

    # 1. Iniciar server local para capturar callback
    server = http.server.HTTPServer(("localhost", 8090), OAuthHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    # 2. Abrir browser con URL de autorización
    auth_params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"{AUTH_URL}?{auth_params}"

    print("\nAbriendo browser para autorizar YouTube...")
    print(f"Si no se abre, visitá: {auth_url}\n")
    webbrowser.open(auth_url)

    # 3. Esperar callback
    thread.join(timeout=120)
    server.server_close()

    if not OAuthHandler.auth_code:
        print("Error: No se recibió código de autorización (timeout 120s)")
        sys.exit(1)

    print("Codigo recibido. Intercambiando por tokens...")

    # 4. Intercambiar code por tokens
    r = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": OAuthHandler.auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }, timeout=30)

    if r.status_code != 200:
        print(f"Error obteniendo tokens: {r.status_code} {r.text}")
        sys.exit(1)

    tokens = r.json()
    refresh_token = tokens.get("refresh_token", "")
    access_token = tokens.get("access_token", "")

    if not refresh_token:
        print("Error: No se obtuvo refresh_token. Intentá de nuevo con prompt=consent.")
        sys.exit(1)

    # 5. Verificar que funciona
    me = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if me.status_code == 200:
        items = me.json().get("items", [])
        if items:
            channel_name = items[0]["snippet"]["title"]
            print(f"\nCanal verificado: {channel_name}")

    # 6. Guardar en .env
    env_path = os.path.normpath(ENV_PATH)
    with open(env_path) as f:
        content = f.read()

    if "YOUTUBE_REFRESH_TOKEN=REEMPLAZAR" in content:
        content = content.replace("YOUTUBE_REFRESH_TOKEN=REEMPLAZAR", f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
    elif "YOUTUBE_REFRESH_TOKEN=" in content:
        import re
        content = re.sub(r"YOUTUBE_REFRESH_TOKEN=.*", f"YOUTUBE_REFRESH_TOKEN={refresh_token}", content)
    else:
        content += f"\nYOUTUBE_REFRESH_TOKEN={refresh_token}\n"

    with open(env_path, "w") as f:
        f.write(content)

    print(f"\nRefresh token guardado en .env")
    print(f"Token: {refresh_token[:20]}...{refresh_token[-10:]}")
    print("\nYouTube configurado exitosamente.")


if __name__ == "__main__":
    main()
