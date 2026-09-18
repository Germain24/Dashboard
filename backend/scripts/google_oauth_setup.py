"""Obtenir un refresh_token Google Calendar (intégration Agenda #83).

Flux OAuth « Desktop app » avec redirection loopback — aucune dépendance hors
stdlib. À lancer une seule fois :

    python backend/scripts/google_oauth_setup.py --client-id XXX --client-secret YYY

Prérequis côté Google Cloud (≈10 min, une fois) :
  1. https://console.cloud.google.com → créer/choisir un projet.
  2. « APIs & Services » → « Enable APIs » → activer **Google Calendar API**.
  3. « OAuth consent screen » → type « External », ajoute ton email en « test user ».
  4. « Credentials » → « Create credentials » → « OAuth client ID » →
     type **Desktop app**. Note le client_id et le client_secret.
  5. Lance ce script avec ces deux valeurs ; autorise dans le navigateur.
  6. Copie les 4 lignes affichées dans ton fichier `.env` à la racine du repo.

Le refresh_token est durable : tu n'as à faire ça qu'une fois.
"""

from __future__ import annotations

import argparse
import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/calendar"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"

_received: dict[str, str] = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _received["code"] = params.get("code", [""])[0]
        _received["state"] = params.get("state", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<h2>Autorisation reçue ✓</h2><p>Tu peux fermer cet onglet et revenir au terminal.</p>".encode("utf-8")
        )

    def log_message(self, *args):  # silencieux
        pass


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description="Obtenir un refresh_token Google Calendar")
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    ap.add_argument("--calendar-id", default="primary", help="ID du calendrier (défaut: primary)")
    args = ap.parse_args()

    state = secrets.token_urlsafe(16)
    auth = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print("\nOuverture du navigateur pour autoriser l'accès à Google Calendar…")
    print("Si rien ne s'ouvre, colle cette URL dans ton navigateur :\n")
    print(auth + "\n")
    try:
        webbrowser.open(auth)
    except Exception:
        pass

    print("En attente de l'autorisation…")
    # handle_request (lancé en thread) remplit _received ; on attend qu'il finisse.
    import time
    for _ in range(300):  # 5 min max
        if _received.get("code"):
            break
        time.sleep(1)

    code = _received.get("code")
    if not code:
        print("✗ Aucune autorisation reçue (timeout).")
        return 1
    if _received.get("state") != state:
        print("✗ State mismatch — interruption par sécurité.")
        return 1

    tokens = _exchange_code(args.client_id, args.client_secret, code)
    refresh = tokens.get("refresh_token")
    if not refresh:
        print("✗ Pas de refresh_token renvoyé. Réessaie avec prompt=consent (déjà activé) "
              "et assure-toi d'avoir révoqué l'accès précédent si besoin.")
        print("Réponse:", tokens)
        return 1

    print("\n✅ Succès ! Ajoute ces lignes à ton fichier .env (racine du repo) :\n")
    print(f"GOOGLE_CLIENT_ID={args.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={args.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={refresh}")
    print(f"GOOGLE_CALENDAR_ID={args.calendar_id}")
    print("\nPuis redémarre le backend. Onglet Agenda → bouton « Google » pour synchroniser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
