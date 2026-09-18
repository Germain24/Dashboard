"""Construction du réservoir : produits Super C rattachés à CIQUAL."""
from __future__ import annotations

import pytest

from app.services.sante.ciqual_matching import CiqualIndex
from app.services.sante.ciqual_matching import Match
from app.services.sante.reservoir import (
    build_reservoir,
    optimizer_product_is_eligible,
    price_per_100g,
)

CIQUAL_ROWS = [
    {"CiqualCode": "1", "CiqualNom": "Cheddar", "CiqualGroupe": "produits laitiers et assimilés"},
    {"CiqualCode": "2", "CiqualNom": "Farine de maïs", "CiqualGroupe": "produits céréaliers"},
    {"CiqualCode": "3", "CiqualNom": "Saumon, cru", "CiqualGroupe": "viandes, œufs, poissons et assimilés"},
]
TENEURS = {
    "1": {"Energie": 400.0, "Proteines": 25.0, "Calcium": 720.0},
    "2": {"Energie": 360.0, "Proteines": 7.0, "Calcium": 5.0},
    "3": {"Energie": 180.0, "Proteines": 20.0, "Calcium": 10.0},
}


@pytest.fixture
def index():
    return CiqualIndex(CIQUAL_ROWS)


class TestPrixAu100g:
    def test_prix_direct(self):
        assert price_per_100g({"price_per_100g": 1.75}) == pytest.approx(1.75)

    def test_derive_du_prix_au_kilo(self):
        assert price_per_100g({"unit": "kg", "unit_price": 17.5}) == pytest.approx(1.75)

    def test_produit_non_chiffrable_est_ecarte(self):
        """Une douzaine d'œufs ou une laitue se vendent à l'unité : aucun poids
        n'est dérivable, on refuse de le deviner."""
        assert price_per_100g({"price": 4.99, "format": "12 un"}) is None
        assert price_per_100g({"price_per_100g": 0}) is None


def test_un_produit_chiffre_et_rattache_entre_avec_ses_teneurs(index):
    lignes, stats = build_reservoir(
        [{"name": "Black Diamond Fromage cheddar fort", "sku": "111", "price_per_100g": 1.75}],
        index, TENEURS,
    )
    assert stats.retenus == 1
    ligne = lignes[0]
    assert ligne["Calcium"] == pytest.approx(720.0)
    assert ligne["Prix"] == pytest.approx(1.75)
    assert ligne["CiqualNom"] == "Cheddar"
    assert ligne["Source"] == "superc"


def test_un_produit_sans_prix_est_ecarte(index):
    _lignes, stats = build_reservoir(
        [{"name": "Fromage cheddar fort", "sku": "111"}], index, TENEURS,
    )
    assert stats.retenus == 0
    assert stats.sans_prix == 1


def test_un_produit_sans_rattachement_sur_est_ecarte(index):
    """Plutôt aucun aliment qu'un aliment aux teneurs d'un autre : l'optimiseur
    cherche la densité par dollar, il irait droit sur la ligne erronée."""
    _lignes, stats = build_reservoir(
        [{"name": "Papier hygiénique ultra doux", "sku": "999", "price_per_100g": 0.5}],
        index, TENEURS,
    )
    assert stats.retenus == 0
    assert stats.non_rattaches == 1


def test_les_variantes_d_un_meme_produit_sont_dedupliquees_au_moins_cher(index):
    """Super C référence le même article sous plusieurs UPC. Deux entrées
    identiques consommeraient deux places de la présélection pour un aliment."""
    lignes, stats = build_reservoir(
        [
            {"name": "Selection Farine de maïs", "sku": "1", "price_per_100g": 0.90},
            {"name": "Selection Farine de maïs", "sku": "2", "price_per_100g": 0.40},
            {"name": "Selection farine de  maïs", "sku": "3", "price_per_100g": 0.70},
        ],
        index, TENEURS,
    )
    assert stats.retenus == 1
    assert stats.doublons == 2
    assert lignes[0]["Prix"] == pytest.approx(0.40)  # la moins chère gagne


def test_par_ciqual_le_moins_cher_gagne_seulement_parmi_les_plus_proches():
    class FakeIndex:
        entries = []

        def match(self, nom, _rayon=""):
            confiance = {"Très proche cher": 0.98,
                          "Proche abordable": 0.95,
                          "Plus loin presque gratuit": 0.80}[nom]
            return Match("1", "Cheddar", "produits laitiers et assimilés", confiance)

    produits = [
        {"name": "Très proche cher", "sku": "1", "price_per_100g": 2.00},
        {"name": "Proche abordable", "sku": "2", "price_per_100g": 1.50},
        {"name": "Plus loin presque gratuit", "sku": "3", "price_per_100g": 0.10},
    ]
    lignes, stats = build_reservoir(
        produits, FakeIndex(), TENEURS, ciqual_candidates=2,
        max_squared_distance=0.0625,
    )
    assert len(lignes) == 1
    assert lignes[0]["Aliment"] == "Proche abordable"
    assert lignes[0]["Prix"] == pytest.approx(1.50)
    assert stats.alternatives_ciqual == 2


def test_distance_quadratique_maximale_ecarte_un_produit_trop_lointain():
    class FakeIndex:
        entries = []

        def match(self, _nom, _rayon=""):
            return Match("1", "Cheddar", "produits laitiers et assimilés", 0.70)

    lignes, stats = build_reservoir(
        [{"name": "Produit éloigné", "sku": "1", "price_per_100g": 0.01}],
        FakeIndex(), TENEURS, min_confidence=0.0,
        max_squared_distance=0.0625,
    )
    assert lignes == []
    assert stats.non_rattaches == 1


def test_un_aliment_deja_cure_n_est_pas_duplique(index):
    """Le catalogue curé est prioritaire : on ne crée pas un homonyme à côté."""
    lignes, _stats = build_reservoir(
        [{"name": "Cheddar", "sku": "111", "price_per_100g": 1.75}],
        index, TENEURS, exclure=frozenset({"Cheddar"}),
    )
    assert lignes[0]["Aliment"] != "Cheddar"


def test_le_nom_du_sitemap_sert_au_rattachement_pas_a_l_affichage(index):
    """Le sitemap donne un nom sans marque, bien meilleur pour rattacher ; le
    libellé commercial reste ce que l'utilisateur voit dans sa liste."""
    lignes, stats = build_reservoir(
        [{"name": "Black Diamond Vieux Fort Extra", "sku": "111", "price_per_100g": 1.75}],
        index, TENEURS, nom_sitemap_par_upc={"111": "fromage cheddar fort"},
    )
    assert stats.retenus == 1
    assert lignes[0]["Aliment"] == "Black Diamond Vieux Fort Extra"
    assert lignes[0]["CiqualNom"] == "Cheddar"


def test_congelable_et_creamiok_suivent_le_groupe_ciqual(index):
    lignes, _ = build_reservoir(
        [{"name": "Saumon atlantique cru", "sku": "1", "price_per_100g": 3.0}],
        index, TENEURS,
    )
    assert lignes[0]["Congelable"] == 1   # viandes/poissons : oui
    assert lignes[0]["CreamiOk"] == 0     # pas un candidat CREAMi


def test_les_rattachements_faibles_sont_rapportes_pas_silencieux(index):
    """Ce qui est écarté doit rester visible : ce sont les meilleurs candidats
    à une saisie manuelle."""
    _lignes, stats = build_reservoir(
        [{"name": "Tartinade à saveur de cheddar et oignon", "sku": "7",
          "price_per_100g": 2.0}],
        index, TENEURS, min_confidence=0.99,
    )
    assert stats.retenus == 0
    assert stats.faible_confiance
    assert "cheddar" in stats.faible_confiance[0]["ciqual"].lower()


def test_override_verifie_corrige_aussi_les_futurs_rebuilds():
    rows = [{
        "CiqualCode": "9821", "CiqualNom": "Pâtes sèches, aux oeufs, crues",
        "CiqualGroupe": "produits céréaliers",
    }]
    lignes, stats = build_reservoir(
        [{"name": "Aurora Pâtes pappardelle aux œufs", "sku": "42",
          "price_per_100g": 1.2}],
        CiqualIndex(rows), {"9821": {"Energie": 370.0, "Proteines": 14.0}},
        min_confidence=0.99,
    )
    assert stats.retenus == 1
    assert lignes[0]["CiqualCode"] == "9821"
    assert lignes[0]["Energie"] == pytest.approx(370.0)


@pytest.mark.parametrize("name", [
    "Arctic Glacier Sac de glace",
    "Gatorade Boisson pour sportifs citron-lime",
    "Lavazza Café moulu qualita rossa",
    "Knox Gélatine originale",
    "Del Monte Barres glacées à la fraise",
    "Selection Croustilles ondulées nature",
    "Selection Croissants natures",
    "Selection Marmelade d'oranges",
    "Paris Pâté Pâté de foie",
    "Campbell's Bouillon de bœuf prêt à utiliser",
    "Selection Bicarbonate de soude",
    "Selection Sauce barbecue",
    "Selection Vinaigre balsamique de Modène",
    "Irrésistible Crevettes tempura surgelées",
    "Maple Leaf Saucisses viennoises",
    "McCain Bouchées de pommes de terre chili et ail surgelées",
    "Mieux-Être Piment de cayenne biologique en sachet",
    "Selection Coriandre moulue",
    "McCain Pizza Pochettes aux trois fromages surgelées",
    "Poulet BBQ cuit chaud",
])
def test_produits_non_interpretables_ou_ultra_transformes_sont_exclus(name):
    assert optimizer_product_is_eligible({"name": name}) is False


@pytest.mark.parametrize("name", [
    "Haricots jaunes", "Lucky Koi Vermicelles de riz",
    "Oeufs", "Flocons d'avoine", "Saumon atlantique",
])
def test_aliments_de_base_restent_admissibles(name):
    assert optimizer_product_is_eligible({"name": name}) is True
