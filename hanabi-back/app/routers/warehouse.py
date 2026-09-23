"""Routes de lecture de l'entrepôt décisionnel. La logique vit dans `app/warehouse.py`.

Réservées aux administrateurs, compte vitrine en lecture seule compris : rien
n'y écrit. Le compte vitrine, public, ne lit que les agrégats.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import warehouse
from ..database import get_db
from ..deps import get_admin_user, is_readonly_admin
from ..ratelimit import limiter

router = APIRouter(prefix="/admin/warehouse", tags=["admin"])

ENTREPOT_ABSENT = (
    "L'entrepôt n'est pas construit sur cette base. "
    "Lance « python dwh.py build » depuis hanabi-dwh/, sur PostgreSQL."
)


def _schemas_du_compte(admin) -> frozenset[str]:
    """Schémas lisibles à la console pour ce compte."""
    if is_readonly_admin(admin):
        return warehouse.SCHEMAS_DEMONSTRATION
    return warehouse.SCHEMAS_AUTORISES


class RequeteSql(BaseModel):
    # Borne de taille du corps ; les barrières sont dans warehouse.executer_sql
    sql: str = Field(min_length=1, max_length=20_000)
    limite: int = Field(
        warehouse.LIMITE_SQL_DEFAUT, ge=1, le=warehouse.LIMITE_SQL_MAX
    )


@router.get("")
def etat_entrepot(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Couches, tables et date de construction. 200 même sans entrepôt (`disponible`)."""
    return warehouse.etat(db)


@router.get("/marts/{cle}")
def contenu_mart(
    cle: str,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    limite: int = Query(warehouse.LIMITE_DEFAUT, ge=1, le=warehouse.LIMITE_MAX),
    decalage: int = Query(0, ge=0),
    # Vérifié ensuite contre le schéma réel de la table
    tri: str | None = Query(None, max_length=63),
    sens: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Contenu d'une table d'agrégats, avec le SQL qui l'a produit."""
    try:
        return warehouse.interroger(
            db, cle, limite=limite, decalage=decalage, tri=tri, sens=sens
        )
    except warehouse.MartInconnu:
        raise HTTPException(404, f"Table d'entrepôt inconnue : {cle}.")
    except warehouse.EntrepotAbsent:
        # 409 : la table est déclarée, pas encore construite
        raise HTTPException(409, ENTREPOT_ABSENT)


# Le compte vitrine est public et chaque requête peut tenir une connexion
# 5 s : sans limite de débit, une boucle assécherait le pool (10 connexions).
@router.post("/sql")
@limiter.limit("12/minute")
def executer_sql(
    request: Request,
    corps: RequeteSql,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    """Lecture libre sur les schémas de l'entrepôt. 422 si la requête est refusée."""
    try:
        return warehouse.executer_sql(
            db, corps.sql, limite=corps.limite, schemas=_schemas_du_compte(admin)
        )
    except warehouse.SqlRefuse as refus:
        raise HTTPException(422, str(refus))
    except warehouse.EntrepotAbsent:
        raise HTTPException(409, ENTREPOT_ABSENT)


# (titre, schémas lus, requête) : un exemple n'est proposé qu'au compte qui peut l'exécuter
EXEMPLES = (
    (
        "Mois où la marge dépasse la moitié du chiffre",
        {"gold"},
        "select mois, ca_cents, marge_cents, taux_marge\n"
        "from gold.gold_kpi_mensuel\n"
        "where taux_marge > 0.5\n"
        "order by mois desc",
    ),
    (
        "Villes qui achètent le plus",
        {"gold"},
        "select ville,\n"
        "       sum(clients) as clients,\n"
        "       sum(ca_cents) as ca_cents,\n"
        "       round(sum(ca_cents)::numeric / nullif(sum(clients), 0)) as valeur_par_client_cents\n"
        "from gold.gold_demographie_clients\n"
        "group by ville\n"
        "having sum(clients) > 50\n"
        "order by valeur_par_client_cents desc",
    ),
    (
        "De gold à silver : le détail d'un segment",
        {"gold", "silver"},
        "select c.segment, count(distinct l.commande_id) as commandes,\n"
        "       sum(l.marge_cents) as marge_cents\n"
        "from gold.gold_clients_rfm c\n"
        "join silver.slv_lignes_commande l on l.client_id = c.client_id\n"
        "where l.est_ca\n"
        "group by c.segment\n"
        "order by marge_cents desc",
    ),
    (
        "Poids de chaque segment dans le chiffre",
        {"gold"},
        "select segment, count(*) as clients,\n"
        "       sum(montant_cents) as ca_cents,\n"
        "       round(avg(frequence), 2) as commandes_moyennes\n"
        "from gold.gold_clients_rfm\n"
        "group by segment\n"
        "order by ca_cents desc",
    ),
    (
        "Historique des contrôles de l'entrepôt",
        {"controles"},
        "select execute_le, titre, reussi, message\n"
        "from controles.journal\n"
        "order by execute_le desc",
    ),
    (
        "Paires de produits qui se substituent (lift < 1)",
        {"gold"},
        "select produit_a, produit_b, lift, support\n"
        "from gold.gold_affinites_produits\n"
        "where lift < 1\n"
        "order by lift asc",
    ),
)


@router.get("/sql/aide")
def aide_sql(admin=Depends(get_admin_user)):
    """Règles de la console et exemples prêts à modifier, selon les droits du compte."""
    ouverts = _schemas_du_compte(admin)
    liste = ", ".join(sorted(ouverts))
    regles = [
        "Lecture seule : la requête commence par SELECT ou WITH.",
        "Une seule instruction à la fois.",
        f"Schémas lisibles : {liste}.",
        f"Interrompue au-delà de {warehouse.DELAI_MAX_MS // 1000} secondes.",
    ]
    if ouverts != warehouse.SCHEMAS_AUTORISES:
        regles.append(
            "Compte de démonstration : bronze et silver, une ligne par client, restent fermés."
        )
    return {
        "schemas": sorted(ouverts),
        "delai_max_s": warehouse.DELAI_MAX_MS // 1000,
        "limite_max": warehouse.LIMITE_SQL_MAX,
        "regles": regles,
        "exemples": [
            {"titre": titre, "sql": sql}
            for titre, lus, sql in EXEMPLES
            if lus <= ouverts
        ],
    }
