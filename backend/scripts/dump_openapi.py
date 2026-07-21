"""Écrit le schéma OpenAPI de l'app dans un fichier, sans lancer de serveur.

Utilisé par la CI (§6.3) pour régénérer `frontend/lib/types.ts` et vérifier
qu'il ne dérive pas du backend. `npm run gen:types` interroge un uvicorn en
cours d'exécution : inutilisable en CI, d'où ce dump direct.

    uv run python -m scripts.dump_openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    # Format identique au `frontend/openapi.json` commité (une ligne, séparateurs
    # par défaut, pas de newline final) : sinon la comparaison de §6.3 remonte
    # 29k lignes de diff purement cosmétique.
    dest.write_text(json.dumps(schema), encoding="utf-8", newline="")
    print(f"{dest} ({len(schema.get('paths', {}))} routes)")


if __name__ == "__main__":
    main()
