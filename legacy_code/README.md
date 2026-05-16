# Legacy code — référence pour le portage

Ce dossier contient l'ancien code Streamlit de Mission Control,
copié depuis le backup `C:\Users\germa\Desktop\Sauvegarde\` après la CONV 1.

**Ce code n'est PAS exécuté.** Il sert uniquement de référence aux conversations
de portage (CONV 2 à CONV 11) pour reprendre les formules métier, les règles
de calcul et la logique d'affichage.

## Contenu

| Chemin                    | Sert à                                            | CONV  |
|---------------------------|---------------------------------------------------|-------|
| `habits/logic.py`         | Calcul thermique, optimiseur tenue, palette       | 2     |
| `habits/vetements.json`   | Données déjà importées en DB                      | 2     |
| `habits/assets/*.png`     | Pixel art pour les vêtements (23 images)          | 2     |
| `sante/logic.py`          | Calculs nutritionnels, plan macros                | 3     |
| `sante/sante.json`        | Données déjà importées en DB                      | 3     |
| `sante/aliments.csv`      | Données déjà importées en DB                      | 3     |
| `finance/logic.py`        | Wrappers yfinance, calculs portefeuille           | 4     |
| `finance/WarrenBuffetMensuel.py` | Scoring Buffett mensuel (~1 920 lignes)    | 4     |
| `finance/tickers.csv`     | Liste des tickers analysés                        | 4     |
| `finance/params.json`     | Paramètres du scoring Buffett                     | 4     |
| `agenda/logic.py`         | Placeholder (18 lignes — peu utile)               | 5     |
| `Dashboard.py`            | UI Streamlit complète (1 217 lignes)              | 2-5   |

## Règles

1. **Ne pas modifier** ces fichiers — le backup est la source de vérité.
2. **Ne pas importer** depuis ce dossier dans `backend/app/` — c'est du code
   archivé, pas du code de production.
3. Pendant le portage, copier-coller des formules / mappings est OK, mais
   réécrire l'implémentation en SQLModel + FastAPI + React (pas en Streamlit).
4. Une fois qu'un module est porté avec succès dans `backend/app/services/<module>/`
   et `frontend/app/<module>/`, et que les tests passent, on peut **supprimer
   le sous-dossier correspondant** de `legacy_code/` pour signifier "porté ✓".
