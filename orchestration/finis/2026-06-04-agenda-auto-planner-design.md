# Planificateur d'agenda automatique — Design

> Statut : design validé (2026-06-04). Implémentation en cours.
> Projet B (le module Cuisine = projet A, séparé, à faire ensuite).

## Objectif

Tous les jours de cuisine (jeudi, dimanche), au lancement du dashboard, proposer
automatiquement un planning qui place les blocs **déplaçables** (sommeil, repas,
sport, cuisine, révision) autour des blocs **fixes** (travail, cours), en
respectant un ordre de priorité. Aperçu à valider, puis écriture locale et envoi
optionnel vers Google Calendar.

## Cycle & fenêtre

- Un **cycle** va du **lendemain** d'un jour de cuisine jusqu'au **prochain jour
  de cuisine inclus**.
  - Lancé **jeudi** → fenêtre {ven, sam, dim}.
  - Lancé **dimanche** → fenêtre {lun, mar, mer, jeu}.
- Le jour où le planificateur est lancé n'est **jamais** replanifié.
- Chaque fenêtre se termine sur le prochain jour de cuisine, donc son bloc cuisine
  (2h) est posé par le run courant.

## Inventaire des blocs

| Bloc | Durée | Fenêtre horaire | Jours | Règle |
|---|---|---|---|---|
| Travail / cours | fixe | agenda | — | immuable, jamais déplacé |
| Sommeil | 8h | 23:00 → 07:00 | chaque nuit | jamais rogné |
| Repas | 3 × 30 min | 07:30 / 12:30 / 19:30 (± 2h) | chaque jour | peut chevaucher le **travail** |
| Cuisine | 2h | ~16:00 | jeu, dim | jour cuisine de la fenêtre |
| Révision | 2h / cours | n'importe quel créneau libre | — | 2h par cours distinct de la fenêtre (catégorie `cours`, déduit de l'agenda) |
| Sport | 1h30 | 07:30 **ou** 18:00 | lun, mar, mer, ven, sam | créneau libre proche |

- **Tampon** : 15 min vides entre deux blocs consécutifs (sauf repas-sur-travail).
  Pas d'événement « trajet » créé.

## Priorités & sacrifice

Ordre d'importance (du plus protégé au premier sacrifié) :

**Santé (sommeil + repas) > Cuisine > Révision > Sport**

- Placement dans l'ordre de priorité : le prioritaire prend les meilleurs créneaux.
- Un bloc qui ne rentre pas n'est **jamais rogné** : il est **signalé « non placé »**
  dans l'aperçu. Le sport saute en premier quand le cycle déborde.
- La santé n'est jamais sacrifiée.

## Algorithme (placeur glouton, lecture seule)

1. Calculer la fenêtre `[lendemain → prochain jour cuisine inclus]` depuis `run_date`.
2. Charger les fixes de la fenêtre (travail, cours + récurrences déployées).
   Réutiliser le service de créneaux libres existant (`/agenda/slots`).
3. Poser dans l'ordre de priorité :
   - Sommeil 23:00–07:00 chaque nuit.
   - Repas : 30 min au plus proche de l'ancre (± 2h) ; autorisé à chevaucher un
     bloc *travail* (pas les autres blocs).
   - Cuisine : 2h le jour cuisine, au plus proche de 16:00.
   - Révision : 2h par cours distinct, dans n'importe quel créneau libre.
   - Sport : 1h30 les jours sport, à 7h30 ou 18h selon la place.
4. Tampon 15 min réservé entre blocs consécutifs.
5. Tout bloc sans créneau → liste `non_places`.
6. Sortie : `{ fenetre, blocs[], non_places[] }`. Aucune écriture.

## Idempotence

- Chaque bloc écrit est taggé `source="planner"`.
- Avant d'écrire une fenêtre, supprimer les `source="planner"` existants de cette
  fenêtre, puis réécrire. **Jamais** touché : `travail`, `cours`, `entrainement`,
  Google, ou manuel (source ≠ planner).
- `preview` ne modifie rien.

## API

Pas de nouvelle table : les blocs sont des `Evenement` (`source="planner"`,
`categorie` + `couleur` par type).

- `GET /agenda/plan/preview?date=YYYY-MM-DD` → `{ fenetre, blocs[], non_places[] }`, lecture seule.
- `POST /agenda/plan/commit?date=YYYY-MM-DD` → recalcule côté serveur (déterministe),
  supprime les `source="planner"` de la fenêtre, crée les events, renvoie la liste.
- `POST /agenda/plan/push?from=&to=` → pousse les blocs planner vers Google Calendar
  (réutilise `gcalPush`, #83). Désactivé si GCal non configuré. **Différé** (intégration plus tard.)

## UI

- **Déclencheur** : sur le dashboard, les jours de cuisine (jeu/dim) et s'il n'existe
  pas déjà un plan pour la fenêtre, une carte « Nouveau cycle — planifier ». Une entrée
  « Planifier le cycle » reste dispo dans le module Agenda hors jour cuisine.
- **Aperçu** : modal montrant le planning par jour (timeline) + blocs non placés
  surlignés. Boutons : Valider (commit) puis Envoyer sur Google Agenda (push).
- Après commit, carte « Cycle planifié » + lien agenda.

## Cas limites

- GCal non configuré → bouton push désactivé + invite (#83).
- Blocs non placés → listés dans l'aperçu.
- Pas de cours dans la fenêtre → pas de révision.
- Cycle déjà planifié → relancer remplace (idempotent).
- Sommeil 23→07 → un event à cheval sur deux jours.
- Backend hors ligne → aperçu échoue proprement (message + réessai).

## Tests

- Unitaires du **placeur** (fonction pure) : nombre/durée des blocs, ordre de
  sacrifice (sport signalé d'abord), tampon 15 min, repas-sur-travail, sommeil 23-7,
  rapport des non-placés.
- Idempotence : commit deux fois → seuls les `source=planner` remplacés.
- Agenda vide (tout rentre) et saturé (sport non placé).

## Hors-scope / évolutions

- Aperçu **éditable** (glisser les blocs avant validation) → v2.
- Solveur de contraintes (OR-Tools) si le glouton devient insuffisant → v2.
- Déclenchement par job planifié (APScheduler) plutôt que par ouverture du dashboard → v2.
- Module Cuisine end-to-end (projet A) → séparé.
