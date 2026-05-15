# CONV 12 — Agent IA (chat + tool calling)

## Objectif

Créer le "robot" promis dans la vision : agent IA conversationnel intégré au
dashboard, capable de lire et agir sur tous les modules via tool calling.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée** et idéalement plusieurs modules
implémentés (sinon l'agent n'a rien à faire). Recommandé après Phases 2 et 3.

## Décisions à prendre

1. **LLM backend** :
   - Option A : Claude API (cloud, qualité max, ~10 $/mois)
   - Option B : Ollama local (gratuit, qualité moyenne, dépend du PC)
   - Option C : Hybride (Claude pour le chat, Ollama pour tâches batch)
   - Reco : commencer A, design abstrait pour switch facile vers B.
2. **Modèle Claude** : Sonnet 4.6 (équilibre coût/qualité) ou Opus 4.6 (meilleur
   raisonnement) ?
3. **Persistance des conversations** : SQLite (oui — déjà dispo), avec une
   table `agent_conversations` + `agent_messages`.
4. **Surface tool calling — que peut faire l'agent ?**
   - Lire : tout (portfolio, santé, agenda, garde-robe, études, etc.)
   - Écrire : valider tenue, logger poids, ajouter une transaction budget,
     logger une séance entraînement, cocher une habitude, créer une tâche
     agenda, ajouter une note de livre
   - Lancer : analyse Buffett, génération plan repas, suggestion outfit
   - **Interdit** : pas de transactions financières réelles, pas d'envoi
     d'emails externes
5. **Streaming** : réponses streamées (SSE) ou bloc final ?

## Architecture

### Backend (`backend/app/agent/`)

```
agent/
├── __init__.py
├── server.py              # routes /api/agent
├── llm/
│   ├── base.py            # interface abstraite
│   ├── anthropic.py       # impl Claude
│   └── ollama.py          # impl Ollama (V2)
├── tools/
│   ├── __init__.py        # registry de tools
│   ├── garderobe.py       # tools liés CONV 2
│   ├── sante.py           # tools liés CONV 3
│   ├── finance.py         # CONV 4
│   ├── agenda.py          # CONV 5
│   ├── etudes.py          # CONV 6
│   ├── entrainement.py    # CONV 7
│   ├── budget.py          # CONV 8
│   ├── cuisine.py         # CONV 9
│   ├── habitudes.py       # CONV 10
│   └── livres.py          # CONV 11
├── memory.py              # persistance conversations
└── prompts/
    └── system.md          # prompt système maître
```

### Endpoints

```
POST   /api/agent/chat               # message → réponse (streaming SSE)
GET    /api/agent/conversations
GET    /api/agent/conversations/{id}
DELETE /api/agent/conversations/{id}
GET    /api/agent/tools              # liste introspectable des tools
```

### Frontend (`frontend/app/robot/`)

- Layout chat plein écran
- Historique conversations dans la sidebar (groupé par jour)
- Affichage des tool calls dans la conversation (cards pliables)
- Markdown rendering des réponses
- Bouton "Nouvelle conversation"

## Conception des tools

Chaque tool est une fonction Python annotée typée, exposée au LLM via le format
tool-use Anthropic. Le SDK officiel `anthropic` permet de définir les tools
directement depuis les signatures. Exemple :

```python
@tool
def get_today_outfit() -> dict:
    """Renvoie la tenue suggérée pour aujourd'hui avec score thermique."""
    ...

@tool
def log_weight(kg: float) -> dict:
    """Enregistre le poids du jour (kg). Re-calcule le plan nutrition."""
    ...
```

## Prompt système (`prompts/system.md`)

Brief :
- Tu es l'assistant personnel de Germain
- Tu as accès à ses modules de vie via tools
- Tu réponds en français (Québec OK)
- Tu n'inventes jamais de données — si tu ne sais pas, tu appelles un tool
- Tu peux agir (écrire, lancer des actions) mais tu confirmes pour les actions
  irréversibles (suppression, etc.)
- Pour les sujets sensibles (finance, santé), tu n'es pas un professionnel —
  tu donnes des informations factuelles depuis ses données

## Hors-scope

- Voice / TTS / STT (V2)
- Connecteurs externes (Telegram, Discord) — l'agent reste dans le dashboard
- RAG sur documents externes (V2)

## Dépendances

- Prérequis : CONV 1, et au moins quelques modules implémentés pour avoir
  des tools utiles.
- Synergique : CONV 13 (jobs auto peuvent utiliser l'agent pour briefings).

## Suggestions techniques

- SDK `anthropic` officiel, pas LangChain (trop lourd pour un usage perso).
- SSE via `sse-starlette` pour le streaming.
- Côté front : `useEffect` + `EventSource` pour consommer SSE.
- Stocker l'historique en SQLite, pas en mémoire (perdu au redémarrage).
- Logger toutes les requêtes + tokens consommés pour suivi coût.

## Critères de succès

- [ ] "Qu'est-ce que j'ai à manger aujourd'hui ?" → l'agent appelle le tool
  nutrition et répond avec le plan
- [ ] "J'ai pesé 78.2 ce matin" → l'agent appelle `log_weight`, confirme
- [ ] "Trouve-moi un créneau de 1h cet aprem pour la muscu" → l'agent appelle
  l'agenda et propose des slots
- [ ] Le coût mensuel reste sous 10 $ en usage normal
- [ ] Switch Claude ↔ Ollama via variable d'env sans toucher au code

---

## Prompt d'amorce

```
Je veux ajouter l'agent IA à Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV12_agent_ia.md

Pose-moi les 5 questions de "Décisions à prendre".
```
