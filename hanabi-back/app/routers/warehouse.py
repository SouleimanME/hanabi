"""Routes de lecture de l'entrepot decisionnel.

Deux poignees seulement, parce qu'il n'y a que deux questions : de quoi
l'entrepot est-il fait, et que contient telle table. Toute la logique
d'interrogation vit dans `app/warehouse.py` ; ce fichier ne fait que valider
des parametres et traduire deux exceptions en codes HTTP.

Comme le reste de `/admin`, ces routes exigent un compte administrateur. Elles
restent accessibles au compte vitrine en lecture seule : elles ne modifient
rien, et l'entrepot est precisement ce qu'un visiteur vient voir.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import warehouse
from ..database import get_db
from ..deps import get_admin_user

router = APIRouter(prefix="/admin/warehouse", tags=["admin"])


class RequeteSql(BaseModel):
    """Lecture libre soumise par le back-office.

    La borne de longueur n'est pas une mesure de securite - les barrieres sont
    dans `warehouse.executer_sql` - mais elle evite qu'un corps de plusieurs
    mega-octets atteigne l'analyse.
    """

    sql: str = Field(min_length=1, max_length=20_000)
    limite: int = Field(
        warehouse.LIMITE_SQL_DEFAUT, ge=1, le=warehouse.LIMITE_SQL_MAX
    )


@router.get("")
def etat_entrepot(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Couches, tables disponibles et date de la derniere construction.

    Repond 200 meme quand l'entrepot n'existe pas : sur la base SQLite de
    developpement, c'est un etat normal et non une panne. L'interface s'appuie
    sur le drapeau `disponible` pour afficher la marche a suivre plutot qu'un
    message d'erreur.
    """
    return warehouse.etat(db)


@router.get("/marts/{cle}")
def contenu_mart(
    cle: str,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    limite: int = Query(warehouse.LIMITE_DEFAUT, ge=1, le=warehouse.LIMITE_MAX),
    decalage: int = Query(0, ge=0),
    # Le tri est un nom de colonne, verifie ensuite contre le schema reel de la
    # table. La borne de longueur n'est la que pour ecarter d'emblee une valeur
    # manifestement fantaisiste avant qu'elle n'atteigne la base.
    tri: str | None = Query(None, max_length=63),
    sens: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Contenu d'une table d'agregats, avec le SQL qui l'a produit."""
    try:
        return warehouse.interroger(
            db, cle, limite=limite, decalage=decalage, tri=tri, sens=sens
        )
    except warehouse.MartInconnu:
        raise HTTPException(404, f"Table d'entrepot inconnue : « {cle} ».")
    except warehouse.EntrepotAbsent:
        # 409 et non 404 : la table existe dans le projet, elle n'a simplement
        # pas encore ete construite sur cette base. Le message dit quoi faire,
        # ce qu'un 404 laisserait deviner.
        raise HTTPException(
            409,
            "L'entrepot n'a pas ete construit sur cette base. "
            "Lance « python dwh.py build » depuis hanabi-dwh/, sur une base PostgreSQL.",
        )


@router.post("/sql")
def executer_sql(
    corps: RequeteSql,
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
):
    """Execute une lecture libre sur les schemas de l'entrepot.

    Reste accessible au compte vitrine en lecture seule, et c'est coherent :
    la console ne peut rien modifier, et interroger l'entrepot soi-meme est
    precisement ce qu'un visiteur vient voir. Les barrieres qui comptent - la
    transaction en lecture seule, le delai d'execution, l'examen du plan - ne
    dependent d'aucun role.

    422 pour une requete refusee, et non 400 : c'est bien la donnee envoyee qui
    est en cause, et l'interface affiche le message tel quel. Il dit toujours
    quoi corriger.
    """
    try:
        return warehouse.executer_sql(db, corps.sql, limite=corps.limite)
    except warehouse.SqlRefuse as refus:
        raise HTTPException(422, str(refus))
    except warehouse.EntrepotAbsent:
        raise HTTPException(
            409,
            "L'entrepot n'a pas ete construit sur cette base. "
            "Lance « python dwh.py build » depuis hanabi-dwh/, sur une base PostgreSQL.",
        )


@router.get("/sql/aide")
def aide_sql(_=Depends(get_admin_user)):
    """De quoi ecrire une requete sans quitter l'ecran.

    Les regles de la console et quelques exemples qui marchent. Une console SQL
    sans rien pour demarrer suppose qu'on connait deja le schema par coeur ;
    ces exemples sont la pour qu'on puisse les modifier plutot que les ecrire.
    """
    return {
        "schemas": sorted(warehouse.SCHEMAS_AUTORISES),
        "delai_max_s": warehouse.DELAI_MAX_MS // 1000,
        "limite_max": warehouse.LIMITE_SQL_MAX,
        "regles": [
            "Lecture seule : la requete commence par SELECT ou WITH.",
            "Une seule instruction a la fois.",
            f"Seuls les schemas {', '.join(sorted(warehouse.SCHEMAS_AUTORISES))} sont lisibles.",
            f"Interrompue au-dela de {warehouse.DELAI_MAX_MS // 1000} secondes.",
        ],
        "exemples": [
            {
                "titre": "Les mois ou la marge a depasse la moitie du chiffre",
                "sql": (
                    "select mois, ca_cents, marge_cents, taux_marge\n"
                    "from gold.gold_kpi_mensuel\n"
                    "where taux_marge > 0.5\n"
                    "order by mois desc"
                ),
            },
            {
                "titre": "Les villes qui achetent le plus, tous ages confondus",
                "sql": (
                    "select ville,\n"
                    "       sum(clients) as clients,\n"
                    "       sum(ca_cents) as ca_cents,\n"
                    "       round(sum(ca_cents)::numeric / nullif(sum(clients), 0)) as valeur_par_client_cents\n"
                    "from gold.gold_demographie_clients\n"
                    "group by ville\n"
                    "having sum(clients) > 50\n"
                    "order by valeur_par_client_cents desc"
                ),
            },
            {
                "titre": "Remonter de gold jusqu'a silver : le detail derriere un segment",
                "sql": (
                    "select c.segment, count(distinct l.commande_id) as commandes,\n"
                    "       sum(l.marge_cents) as marge_cents\n"
                    "from gold.gold_clients_rfm c\n"
                    "join silver.slv_lignes_commande l on l.client_id = c.client_id\n"
                    "where l.est_ca\n"
                    "group by c.segment\n"
                    "order by marge_cents desc"
                ),
            },
            {
                "titre": "Les paires de produits qui se substituent (lift < 1)",
                "sql": (
                    "select produit_a, produit_b, lift, support\n"
                    "from gold.gold_affinites_produits\n"
                    "where lift < 1\n"
                    "order by lift asc"
                ),
            },
        ],
    }
