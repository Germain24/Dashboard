import datetime as dt
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class SkincareProduct(SQLModel, table=True):
    __tablename__ = "skincare_product"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    type: str = "autre"  # nettoyant|serum|hydratant|spf|exfoliant|masque|retinoide|autre
    moment: str = "AM"   # AM|PM|les_deux
    ordre: int = 0       # position dans la routine du moment
    # Fréquence
    frequence_type: str = "quotidien"  # quotidien|hebdo_jours|n_par_semaine
    frequence_jours: str | None = None  # ex. "0,3" (lun, jeu) si hebdo_jours
    frequence_n: int | None = None      # ex. 2 si n_par_semaine
    # Contraintes de placement (pour l'orchestrateur, phases suivantes)
    apres_douche: bool = False
    soir_seulement: bool = False
    pas_avant_soleil: bool = False
    duree_min: int = 2
    # Stock / péremption / coût
    stock_qte: float | None = None
    unite: str | None = None
    date_ouverture: dt.date | None = None
    date_peremption: dt.date | None = None
    cout: float = 0.0
    actif: bool = True


class SkincareLog(SQLModel, table=True):
    __tablename__ = "skincare_log"
    id: int | None = Field(default=None, primary_key=True)
    date_jour: dt.date
    moment: str  # AM|PM
    produits_ids: str = ""  # CSV des ids appliqués
    note: str | None = None
    __table_args__ = (UniqueConstraint("date_jour", "moment"),)
