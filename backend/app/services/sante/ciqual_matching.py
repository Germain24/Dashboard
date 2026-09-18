"""Rattache un produit Super C à l'aliment CIQUAL le plus proche.

Le magasin vend des produits de marque (« Sélection Chocolat au lait
protéiné ») ; CIQUAL décrit des aliments génériques (« Chocolat au lait »).
Ce module fait le pont, pour que l'optimiseur puisse considérer des produits
réellement en rayon plutôt que les seuls 114 aliments saisis à la main.

Méthode : recouvrement de tokens pondéré par IDF (un token rare comme
« quinoa » discrimine, « bio » ou « nature » non), accéléré par un index
inversé, puis modulé par la concordance entre le rayon Super C et le groupe
CIQUAL. Un score de confiance dans [0, 1] accompagne TOUJOURS le résultat.

Pourquoi la confiance compte plus que le score : l'optimiseur maximise la
densité nutritionnelle par dollar. Un mauvais rattachement ne produit pas une
erreur discrète — il crée un aliment faussement extraordinaire, que l'optimiseur
ira chercher en priorité. Mieux vaut ne pas rattacher que mal rattacher, d'où
`MIN_CONFIDENCE` et l'absence totale de repli « au moins ça ».

Logique PURE : aucune I/O, aucune horloge. Testable de bout en bout.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

#: En dessous, on préfère ne rien rattacher (cf. docstring).
MIN_CONFIDENCE = 0.35

#: Mots vides du français commercial : présents partout, ils ne discriminent
#: rien et gonflent artificiellement les scores.
STOPWORDS: frozenset[str] = frozenset({
    "de", "du", "des", "la", "le", "les", "l", "d", "au", "aux", "a", "en",
    "et", "ou", "avec", "sans", "pour", "sur", "par", "un", "une", "the",
    "of", "and", "style", "type", "saveur", "gout", "veritable", "qualite",
    "grand", "petit", "grande", "petite", "nouveau", "nouvelle", "format",
    "paquet", "sachet", "boite", "sac", "pot", "emballe", "emballee",
    "prete", "pret", "pratique", "delicieux", "delicieuse",
})

#: Mentions marketing/logistiques sans valeur nutritionnelle discriminante.
#: Retirées AVANT le calcul : « bio » n'aide pas à choisir entre une pomme et
#: un yogourt, mais il tirerait vers les entrées CIQUAL qui le mentionnent.
NOISE_TOKENS: frozenset[str] = frozenset({
    "bio", "biologique", "organique", "naturel", "naturelle", "nature",
    "original", "originale", "classique", "traditionnel", "traditionnelle",
    "premium", "selection", "choix", "maison", "familial", "familiale",
    "econo", "economique", "value", "essentiel", "essentiels",
    "surgele", "surgelee", "surgeles", "surgelees", "congele", "congelee",
    "frais", "fraiche", "refrigere", "refrigeree",
    "ml", "l", "g", "kg", "mg", "cl", "oz", "lb", "un", "unites", "portions",
})

#: Rayon Super C -> groupes CIQUAL plausibles. La concordance vaut un bonus
#: multiplicatif ; la discordance, un malus. Objectif : empêcher un « lait de
#: coco » du rayon boissons d'atterrir sur une conserve de viande au curry
#: simplement parce qu'ils partagent le token « coco ».
RAYON_TO_GROUPES: dict[str, frozenset[str]] = {
    "fruits-et-legumes": frozenset({"fruits, légumes, légumineuses et oléagineux"}),
    "viandes-et-volailles": frozenset({"viandes, œufs, poissons et assimilés"}),
    "poissons-et-fruits-de-mer": frozenset({"viandes, œufs, poissons et assimilés"}),
    "produits-laitiers-et-oeufs": frozenset({
        "produits laitiers et assimilés", "viandes, œufs, poissons et assimilés",
    }),
    "boissons": frozenset({"eaux et autres boissons", "produits laitiers et assimilés"}),
    "pains-et-patisseries": frozenset({"produits céréaliers", "produits sucrés"}),
    "collations": frozenset({
        "produits sucrés", "produits céréaliers",
        "fruits, légumes, légumineuses et oléagineux",
    }),
    "charcuteries-et-plats-prepares": frozenset({
        "entrées et plats composés", "viandes, œufs, poissons et assimilés",
    }),
    "plats-cuisines": frozenset({"entrées et plats composés"}),
    "produits-surgeles": frozenset({
        "entrées et plats composés", "glaces et sorbets",
        "fruits, légumes, légumineuses et oléagineux",
    }),
    "bebe": frozenset({"aliments infantiles"}),
}

#: Bonus/malus appliqués au score selon la concordance rayon ↔ groupe CIQUAL.
GROUP_MATCH_BONUS = 1.25
GROUP_MISMATCH_MALUS = 0.6

#: Synonymes québécois/commerciaux -> vocabulaire CIQUAL (français de France).
#: Sans cette table, « gruau » ne rejoint jamais « flocons d'avoine » et le
#: produit finit non rattaché.
SYNONYMS: dict[str, str] = {
    "gruau": "avoine",
    "canneberge": "airelle",
    "canneberges": "airelle",
    "bleuet": "myrtille",
    "bleuets": "myrtille",
    "atocas": "airelle",
    "creton": "rillettes",
    "cretons": "rillettes",
    "feve": "haricot",
    "feves": "haricot",
    "ble": "ble",
    "boeuf": "boeuf",
    "breuvage": "boisson",
    "liqueur": "soda",
    "croustille": "chips",
    "croustilles": "chips",
    "biscotte": "biscotte",
    "yogourt": "yaourt",
    "yaourts": "yaourt",
    "yogourts": "yaourt",
    "beigne": "beignet",
    "beignes": "beignet",
    "patate": "pomme de terre",
    "patates": "pomme de terre",
    "mais": "mais",
    "arachide": "arachide",
    "arachides": "arachide",
    "sucrerie": "confiserie",
    "grignotine": "chips",
    "grignotines": "chips",
    "jambon": "jambon",
    "poitrine": "poitrine",
    "tofu": "tofu",
    "edulcorant": "edulcorant",
}

#: Malus quand le nom-tête du produit n'apparaît pas dans l'entrée CIQUAL.
#: En français, le premier mot plein porte la nature de l'aliment : des
#: « biscuits à l'avoine » sont des BISCUITS, pas de l'avoine ; un « riz saveur
#: cheddar » est du RIZ, pas du fromage. Sans cette contrainte, un ingrédient
#: cité en second rôle l'emportait dès qu'il était plus rare que le nom-tête.
HEAD_MISMATCH_MALUS = 0.55

_TOKEN_RE = re.compile(r"[a-z0-9]+")
#: Tokens purement numériques ou format (« 500 », « 2x250 ») : jamais informatifs.
_NUMERIC_RE = re.compile(r"^\d+$")

#: Pluriels français à ne PAS singulariser (le « s »/« x » final fait partie du
#: mot) — sinon « ananas » deviendrait « anana » et « riz », « ri ».
_INVARIABLES: frozenset[str] = frozenset({
    "ananas", "riz", "jus", "mais", "anis", "cassis", "couscous", "houmous",
    "epices", "pois", "noix", "choux", "os", "gras", "repas", "biais",
})


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def singularize(token: str) -> str:
    """Singularisation naïve du français : « amandes » -> « amande ».

    Indispensable pour que le magasin (« tortillas », « biscuits ») rejoigne
    CIQUAL, qui nomme ses aliments au singulier. Naïve mais suffisante ici :
    on ne cherche pas une analyse grammaticale, seulement à faire coïncider
    deux vocabulaires. Les mots dont le « s » est radical sont protégés.
    """
    if len(token) <= 3 or token in _INVARIABLES:
        return token
    if token.endswith("aux"):          # journaux -> journal (rare en alimentaire)
        return token[:-3] + "al"
    if token.endswith(("s", "x")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Texte libre -> tokens normalisés, sans accents, bruit ni mots vides.

    Les synonymes sont appliqués APRÈS le nettoyage : leurs valeurs peuvent
    contenir plusieurs mots (« patate » -> « pomme de terre »), qui sont alors
    re-découpés.
    """
    base = strip_accents(str(text or "").lower())
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(base):
        if _NUMERIC_RE.match(raw) or raw in STOPWORDS or raw in NOISE_TOKENS:
            continue
        word = singularize(raw)
        if word in STOPWORDS or word in NOISE_TOKENS:
            continue
        replacement = SYNONYMS.get(raw) or SYNONYMS.get(word)
        if replacement is None:
            tokens.append(word)
            continue
        for part in _TOKEN_RE.findall(strip_accents(replacement)):
            part = singularize(part)
            if part not in STOPWORDS:
                tokens.append(part)
    return tokens


@dataclass(frozen=True)
class CiqualEntry:
    """Une ligne CIQUAL réduite à ce qui sert au rattachement."""
    code: str
    nom: str
    groupe: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class Match:
    code: str
    nom: str
    groupe: str
    confiance: float


class CiqualIndex:
    """Index inversé token -> aliments CIQUAL, avec pondération IDF.

    Un balayage naïf coûterait 6 847 × 3 186 ≈ 22 millions de comparaisons ;
    l'index ne visite que les entrées partageant au moins un token.
    """

    def __init__(self, entries: Iterable[dict]):
        self.entries: list[CiqualEntry] = []
        postings: dict[str, list[int]] = defaultdict(list)

        for row in entries:
            nom = str(row.get("CiqualNom") or "").strip()
            code = str(row.get("CiqualCode") or "").strip()
            if not nom or not code:
                continue
            tokens = tuple(dict.fromkeys(tokenize(nom)))  # dédupliqué, ordre stable
            if not tokens:
                continue
            index = len(self.entries)
            self.entries.append(CiqualEntry(
                code=code, nom=nom,
                groupe=str(row.get("CiqualGroupe") or "").strip(),
                tokens=tokens,
            ))
            for token in tokens:
                postings[token].append(index)

        self.postings: dict[str, list[int]] = dict(postings)
        total = max(1, len(self.entries))
        # IDF lissé : un token présent partout pèse ~0, un token unique pèse le
        # plus. `+1` évite la division par zéro et borne le poids maximal.
        self.idf: dict[str, float] = {
            token: math.log(1.0 + total / (1.0 + len(indices)))
            for token, indices in self.postings.items()
        }
        # Masse IDF totale de chaque entrée. Sert à mesurer quelle PART de
        # l'entrée le produit explique — la moitié du score (cf. `match`).
        self.masses: list[float] = [
            sum(self.idf.get(t, 0.0) for t in e.tokens) or 1.0
            for e in self.entries
        ]

    def __len__(self) -> int:
        return len(self.entries)

    def match(self, nom: str, rayon: str = "") -> Optional[Match]:
        """Meilleur rattachement pour un nom de produit, ou None si trop incertain."""
        tokens = list(dict.fromkeys(tokenize(nom)))
        if not tokens:
            return None

        # Masse IDF du produit, tokens hors vocabulaire CIQUAL COMPRIS : un
        # produit dont l'essentiel du nom est inconnu de CIQUAL ne doit pas
        # obtenir une confiance parfaite sur le seul mot qui, lui, est connu.
        query_mass = sum(self.idf.get(t, 0.0) for t in tokens)
        if query_mass <= 0.0:
            # Aucun token du produit n'existe dans le vocabulaire CIQUAL.
            return None

        shared: dict[int, float] = defaultdict(float)
        for token in tokens:
            weight = self.idf.get(token)
            if weight is None:
                continue
            for index in self.postings[token]:
                shared[index] += weight

        if not shared:
            return None

        groupes_attendus = RAYON_TO_GROUPES.get(rayon)
        tete = tokens[0]
        best_index, best_score = -1, -1.0
        for index, commun in shared.items():
            # Score = moyenne harmonique de DEUX couvertures :
            #   - part du produit expliquée par l'entrée CIQUAL ;
            #   - part de l'entrée CIQUAL expliquée par le produit.
            # Exiger les deux évite les deux travers symétriques du cosinus :
            # « barre de chocolat au lait à la noisette » -> « Noisette »
            # (l'entrée est couverte à 100 %, le produit très peu), et
            # « fondue au chocolat » -> « Fondue de poireau » (le token rare
            # « fondue » suffisait à emporter la décision).
            couverture_produit = commun / query_mass
            couverture_entree = commun / self.masses[index]
            somme = couverture_produit + couverture_entree
            score = 0.0 if somme <= 0 else 2.0 * couverture_produit * couverture_entree / somme
            if tete not in self.entries[index].tokens:
                score *= HEAD_MISMATCH_MALUS
            if groupes_attendus:
                score *= (
                    GROUP_MATCH_BONUS
                    if self.entries[index].groupe in groupes_attendus
                    else GROUP_MISMATCH_MALUS
                )
            if score > best_score:
                best_index, best_score = index, score

        if best_index < 0:
            return None
        entry = self.entries[best_index]
        # Le bonus de groupe peut pousser au-delà de 1 : on borne, la confiance
        # devant rester lisible comme une proportion.
        confiance = min(1.0, best_score)
        if confiance < MIN_CONFIDENCE:
            return None
        return Match(code=entry.code, nom=entry.nom, groupe=entry.groupe,
                     confiance=round(confiance, 4))
