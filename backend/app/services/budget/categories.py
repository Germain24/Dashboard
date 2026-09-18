from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.budget import BudgetCategory

# Les deux racines rendent la lecture des flux explicite. Les identifiants des
# catégories historiques sont conservés lors de leur réorganisation afin que
# les transactions, les règles et les enveloppes continuent de les référencer.
DEFAULT_CATEGORIES = [
    ("Dépenses", None),
    ("Revenus", None),
    # Familles de dépenses
    ("Logement", "Dépenses"),
    ("Transport", "Dépenses"),
    ("Nourriture", "Dépenses"),
    ("Santé", "Dépenses"),
    ("Loisirs", "Dépenses"),
    ("Abonnements", "Dépenses"),
    ("Vêtements & soins", "Dépenses"),
    ("Éducation", "Dépenses"),
    ("Impôts & finances", "Dépenses"),
    ("Maison & achats", "Dépenses"),
    ("Famille & animaux", "Dépenses"),
    ("Voyages", "Dépenses"),
    ("Cadeaux & dons", "Dépenses"),
    ("Investissements & épargne", "Dépenses"),
    ("Dépenses professionnelles", "Dépenses"),
    # Logement
    ("Loyer", "Logement"),
    ("Hypothèque", "Logement"),
    ("Électricité", "Logement"),
    ("Chauffage", "Logement"),
    ("Eau", "Logement"),
    ("Internet", "Logement"),
    ("Assurance habitation", "Logement"),
    ("Entretien du logement", "Logement"),
    ("Meubles et décoration", "Logement"),
    ("Frais de copropriété", "Logement"),
    # Transport
    ("Essence", "Transport"),
    ("Transport en commun", "Transport"),
    ("Taxi et VTC", "Transport"),
    ("Stationnement", "Transport"),
    ("Péages", "Transport"),
    ("Assurance auto", "Transport"),
    ("Entretien auto", "Transport"),
    ("Paiement auto", "Transport"),
    ("Vélo et micromobilité", "Transport"),
    ("Train et avion", "Transport"),
    ("Permis et immatriculation", "Transport"),
    # Nourriture
    ("Épicerie", "Nourriture"),
    ("Supermarché", "Épicerie"),
    ("Marchés et producteurs", "Épicerie"),
    ("Restaurants", "Nourriture"),
    ("Cafés", "Nourriture"),
    ("Livraison", "Nourriture"),
    ("Dépanneur", "Nourriture"),
    ("Alcool", "Nourriture"),
    ("Repas au travail", "Nourriture"),
    # Santé
    ("Pharmacie", "Santé"),
    ("Médicaments", "Santé"),
    ("Médecin", "Santé"),
    ("Dentiste", "Santé"),
    ("Soins visuels", "Santé"),
    ("Thérapie", "Santé"),
    ("Assurance santé", "Santé"),
    ("Sport", "Santé"),
    ("Physiothérapie", "Santé"),
    # Loisirs
    ("Culture", "Loisirs"),
    ("Divertissement", "Loisirs"),
    ("Cinéma", "Culture"),
    ("Livres", "Culture"),
    ("Musique", "Culture"),
    ("Événements", "Culture"),
    ("Sorties", "Divertissement"),
    ("Jeux vidéo", "Divertissement"),
    ("Hobbies", "Divertissement"),
    # Abonnements
    ("Streaming", "Abonnements"),
    ("Téléphone", "Abonnements"),
    ("Logiciels", "Abonnements"),
    ("Stockage infonuagique", "Abonnements"),
    ("Presse", "Abonnements"),
    ("Jeux en ligne", "Abonnements"),
    # Vêtements et soins personnels
    ("Vêtements", "Vêtements & soins"),
    ("Chaussures", "Vêtements & soins"),
    ("Coiffure", "Vêtements & soins"),
    ("Cosmétiques", "Vêtements & soins"),
    ("Hygiène personnelle", "Vêtements & soins"),
    ("Accessoires", "Vêtements & soins"),
    # Éducation
    ("Frais de scolarité", "Éducation"),
    ("Manuels et fournitures", "Éducation"),
    ("Cours et formations", "Éducation"),
    ("Logiciels étudiants", "Éducation"),
    ("Frais d'inscription", "Éducation"),
    # Impôts et services financiers
    ("Impôts", "Impôts & finances"),
    ("Frais bancaires", "Impôts & finances"),
    ("Intérêts d'emprunt", "Impôts & finances"),
    ("Assurance vie", "Impôts & finances"),
    ("Comptabilité", "Impôts & finances"),
    # Maison et achats
    ("Électroménager", "Maison & achats"),
    ("Électronique", "Maison & achats"),
    ("Articles ménagers", "Maison & achats"),
    ("Outils et jardin", "Maison & achats"),
    ("Déménagement", "Maison & achats"),
    # Famille et animaux
    ("Garde d'enfants", "Famille & animaux"),
    ("Fournitures pour enfants", "Famille & animaux"),
    ("Vétérinaire", "Famille & animaux"),
    ("Nourriture pour animaux", "Famille & animaux"),
    ("Garde d'animaux", "Famille & animaux"),
    # Voyages
    ("Transport en voyage", "Voyages"),
    ("Hébergement", "Voyages"),
    ("Restauration en voyage", "Voyages"),
    ("Activités en voyage", "Voyages"),
    ("Assurance voyage", "Voyages"),
    # Cadeaux et dons
    ("Cadeaux", "Cadeaux & dons"),
    ("Dons et charité", "Cadeaux & dons"),
    ("Fêtes et célébrations", "Cadeaux & dons"),
    # Épargne et investissements
    ("Épargne", "Investissements & épargne"),
    ("Épargne de précaution", "Épargne"),
    ("Épargne par projet", "Épargne"),
    ("Bourse", "Investissements & épargne"),
    ("PEA", "Bourse"),
    ("Bourse Direct", "PEA"),
    ("CTO", "Bourse"),
    ("DEGIRO", "CTO"),
    ("IBKR", "CTO"),
    ("Trading 212", "CTO"),
    ("Placements", "Bourse"),
    ("Frais de courtage", "Bourse"),
    ("Comptes enregistrés", "Investissements & épargne"),
    ("REER", "Comptes enregistrés"),
    ("CELI", "Comptes enregistrés"),
    ("Cryptoactifs", "Investissements & épargne"),
    ("Binance", "Cryptoactifs"),
    ("Kraken", "Cryptoactifs"),
    ("Immobilier fractionné", "Investissements & épargne"),
    ("RealT", "Immobilier fractionné"),
    # Dépenses professionnelles
    ("Fournitures professionnelles", "Dépenses professionnelles"),
    ("Déplacements professionnels", "Dépenses professionnelles"),
    ("Repas professionnels", "Dépenses professionnelles"),
    ("Équipement professionnel", "Dépenses professionnelles"),
    # Revenus — une même arborescence permet de classer chaque entrée au détail.
    ("Travail", "Revenus"),
    ("Salaire", "Travail"),
    ("Pourboires", "Travail"),
    ("Heures supplémentaires", "Travail"),
    ("Primes et commissions", "Travail"),
    ("Travail autonome", "Travail"),
    ("Honoraires", "Travail autonome"),
    ("Contrats ponctuels", "Travail autonome"),
    ("Revenus de placements", "Revenus"),
    ("Dividendes", "Revenus de placements"),
    ("Intérêts reçus", "Revenus de placements"),
    ("Intérêts de comptes", "Revenus de placements"),
    ("Remboursements", "Revenus"),
    ("Remboursements reçus", "Remboursements"),
    ("Achats retournés", "Remboursements"),
    ("Frais remboursés", "Remboursements"),
    ("Aides & prestations", "Revenus"),
    ("Prestations et allocations", "Aides & prestations"),
    ("Bourses d'études", "Aides & prestations"),
    ("Revente", "Revenus"),
    ("Vente de biens", "Revente"),
    ("Vente de vêtements", "Revente"),
    ("Vente d'électronique", "Revente"),
    ("Immobilier locatif", "Revenus"),
    ("Revenus locatifs", "Immobilier locatif"),
    ("Cadeaux reçus", "Revenus"),
    ("Autres revenus", "Revenus"),
]

# Déplacements de catégories déjà utilisées. On ne déplace une catégorie que si
# elle se trouve encore à son emplacement historique : un choix personnalisé
# ultérieur reste donc intact au prochain démarrage.
_LEGACY_PARENT_NAMES = {
    "Cinéma": "Loisirs",
    "Livres": "Loisirs",
    "Musique": "Loisirs",
    "Événements": "Loisirs",
    "Sorties": "Loisirs",
    "Jeux vidéo": "Loisirs",
    "Hobbies": "Loisirs",
    "Placements": "Investissements & épargne",
    "Frais de courtage": "Investissements & épargne",
    "REER": "Investissements & épargne",
    "CELI": "Investissements & épargne",
    "Salaire": "Revenus",
    "Primes et commissions": "Revenus",
    "Travail autonome": "Revenus",
    "Dividendes": "Revenus",
    "Intérêts reçus": "Revenus",
    "Prestations et allocations": "Revenus",
    "Remboursements reçus": "Revenus",
    "Vente de biens": "Revenus",
    "Revenus locatifs": "Revenus",
}


def seed_categories(session: Session) -> None:
    by_name: dict[str, list[BudgetCategory]] = {}
    for category in session.exec(select(BudgetCategory)).all():
        by_name.setdefault(category.nom, []).append(category)

    canonical_by_name: dict[str, BudgetCategory] = {}

    def at_parent(nom: str, parent_id: int | None) -> BudgetCategory | None:
        return next(
            (category for category in by_name.get(nom, []) if category.parent_id == parent_id),
            None,
        )

    def register(category: BudgetCategory) -> None:
        by_name.setdefault(category.nom, []).append(category)
        canonical_by_name[category.nom] = category

    # La racine sert de marqueur de migration : les anciens arbres sont
    # réorganisés une seule fois, puis les déplacements faits dans l'interface
    # restent prioritaires au démarrage suivant.
    has_expenses_root = at_parent("Dépenses", None) is not None

    for nom, parent_nom in DEFAULT_CATEGORIES:
        parent = canonical_by_name.get(parent_nom) if parent_nom else None
        category = at_parent(nom, parent.id if parent else None)
        should_reparent = False

        if category is None:
            if parent_nom == "Dépenses" and not has_expenses_root:
                category = at_parent(nom, None)
                should_reparent = category is not None

            old_parent_name = _LEGACY_PARENT_NAMES.get(nom)
            old_parent = canonical_by_name.get(old_parent_name) if old_parent_name else None
            if (
                category is None
                and not has_expenses_root
                and parent is not None
                and old_parent is not None
            ):
                category = at_parent(nom, old_parent.id)
                should_reparent = category is not None

            # Si une catégorie standard a été déplacée manuellement, on la
            # réutilise sans lui imposer à nouveau son emplacement par défaut.
            if category is None and parent_nom is not None:
                candidates = by_name.get(nom, [])
                if len(candidates) == 1:
                    category = candidates[0]

        if category is not None:
            if should_reparent and parent is not None:
                category.parent_id = parent.id
                session.add(category)
                session.commit()
            canonical_by_name[nom] = category
            continue

        category = BudgetCategory(nom=nom, parent_id=parent.id if parent else None)
        try:
            session.add(category)
            session.commit()
            session.refresh(category)
            register(category)
        except IntegrityError:
            session.rollback()
            category = session.exec(select(BudgetCategory).where(BudgetCategory.nom == nom)).first()
            if category is not None:
                canonical_by_name[nom] = category


def get_categories(session: Session) -> list[BudgetCategory]:
    return session.exec(select(BudgetCategory)).all()


def create_category(
    session: Session, nom: str, parent_id: int | None = None, couleur: str = "#6366f1"
) -> BudgetCategory:
    cat = BudgetCategory(nom=nom, parent_id=parent_id, couleur=couleur)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
