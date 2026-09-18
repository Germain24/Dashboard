# Ajouter un ETF ou corriger sa source de composition

Le classeur `data/imports/Finances/tableur/ToutBroker_ETF.xlsx` contient une
feuille d'entrée `ETF_Manuels`. Le programme crée cette feuille au démarrage si
elle n'existe pas. Une ligne décrit **où obtenir** une composition; les
constituants ne sont jamais saisis à la main.

## Colonnes à remplir

Pour un ETF déjà connu, remplir :

- `Actif` = `VRAI`;
- `ETF_ISIN` et `ETF_Ticker`;
- `Indice`;
- `Mode_Composition`;
- `URL_Composition`;
- en mode proxy, `Proxy_ISIN` et `Proxy_Ticker`.

Pour un nouvel ETF, ajouter aussi `Nom`, `MIC` et mettre au moins l'une des
colonnes `BoursDirect2`, `Trading212` ou `IBKR` à `VRAI`.
`Replication_declaree` est une indication; la réplication réellement vérifiée
par les sources officielles reste prioritaire.

### `SOURCE_OFFICIELLE`

`URL_Composition` peut viser un CSV/XLSX officiel ou une page officielle qui
contient un lien non ambigu vers ce fichier. Le tableau doit contenir une
identité de constituant et une colonne de poids explicite couvrant au moins
90 % de l'indice.

### `PROXY_PHYSIQUE`

Indiquer l'ISIN et le ticker d'un ETF physique suivant exactement le même
indice, ainsi que sa page ou son fichier officiel de positions. Le programme
refuse un proxy synthétique, un indice seulement ressemblant ou une couverture
inférieure à 90 %.

## Colonnes automatiques

Ne pas modifier `ETF_Manuels_Statut`, `ETF_Indices` ou
`Indices_Constituants`. Après une analyse, `ETF_Manuels_Statut` indique la
source utilisée, l'URL résolue, le proxy, le nombre de titres, les couvertures
poids et secteur/pays, la date, l'éligibilité et l'erreur éventuelle.

Une instruction manuelle active est autoritaire : si elle est invalide, l'ETF
est exclu avec son erreur au lieu de revenir silencieusement à une autre source.
L'objectif de 100 ETF est un maximum par broker, jamais une raison d'accepter
une composition non vérifiée.
