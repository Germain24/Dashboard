# CONV 11 — Module Livres

## Objectif

Tracker la bibliothèque personnelle : livres lus, en cours, à lire (wishlist).
Notes, citations, sessions de lecture (lié à l'habitude "Lecture 30 min" — CONV 10).

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**.

## Décisions à prendre

1. **Source des métadonnées** : import auto via ISBN (Google Books API,
   Open Library), saisie manuelle, ou les deux ?
2. **Format de prise de notes** : Markdown libre, ou format structuré
   (citation, page, tag) ?
3. **Sessions de lecture** : tu veux logger chaque session (date, durée,
   pages lues) pour alimenter le streak Habitudes ? Ou juste statut on/off ?
4. **Wishlist** : juste une liste, ou avec scoring "envie de lire" + raison ?
5. **Format de lecture** : tracker papier / ebook / audio séparément ?

## Fonctionnalités

### Backend (`backend/app/services/livres/`)

- `books.py` : modèle Book (titre, auteur, isbn, pages, statut, genre,
  format, note finale, dates début/fin)
- `notes.py` : prises de notes (book_id, page, contenu, tags)
- `quotes.py` : citations (book_id, page, texte)
- `sessions.py` : sessions de lecture (book_id, date, durée, pages début/fin)
- `metadata.py` : enrichissement via Google Books / Open Library

### Endpoints

```
GET    /api/livres/books?status=lu|en_cours|a_lire
POST   /api/livres/books
PATCH  /api/livres/books/{id}
DELETE /api/livres/books/{id}

POST   /api/livres/books/from-isbn        # auto-fill métadonnées

GET    /api/livres/books/{id}/notes
POST   /api/livres/books/{id}/notes
PATCH  /api/livres/notes/{id}

GET    /api/livres/books/{id}/quotes
POST   /api/livres/books/{id}/quotes

POST   /api/livres/books/{id}/sessions    # logger une session
                                          # → coche habit "Lecture" si >= 30 min
GET    /api/livres/stats                  # pages/an, par genre, par auteur
```

### Frontend (`frontend/app/livres/`)

- Vue **Bibliothèque** : grille 3 colonnes (à lire / en cours / lu)
- Détail livre : métadonnées, progression %, notes, citations, sessions
- Vue **Statistiques** : pages/an, livres/mois, top genres, top auteurs
- Bouton **+ Ajouter** avec champ ISBN (auto-fill) ou saisie manuelle

## Lien avec Habitudes (CONV 10)

Une session de lecture ≥ 30 min coche automatiquement l'habitude "Lecture".

## Hors-scope

- Synchronisation Goodreads (V2, dépend de leur API)
- Liseuse intégrée (jamais)
- Recommandations IA (l'agent CONV 12 peut le faire à la demande)

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 10 (Habitudes auto-coche).

## Suggestions techniques

- Open Library API gratuite et sans clé : `https://openlibrary.org/api/books?bibkeys=ISBN:...&format=json&jscmd=data`.
- Google Books a une meilleure couverture mais nécessite une clé (gratuite).
- Stocker les couvertures localement (`data/covers/<isbn>.jpg`).

## Critères de succès

- [ ] Ajouter un livre via ISBN auto-remplit titre, auteur, couverture
- [ ] Logger une session 45 min → coche habit Lecture
- [ ] Notes / citations en Markdown rendues correctement
- [ ] Stats "pages lues cette année" calculées
- [ ] Vue mobile lisible

---

## Prompt d'amorce

```
Je veux construire le module Livres de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV11_livres.md

Pose-moi les 5 questions de "Décisions à prendre".
```
