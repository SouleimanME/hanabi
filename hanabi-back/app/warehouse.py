# -*- coding: utf-8 -*-
"""Lecture des tables d'agregats construites par dbt.

Ce module ne calcule rien. C'est la difference avec `analytics.py`, et c'est
tout le propos : les indicateurs sont ici deja calcules, dans le schema `gold`
de la base, par le projet dbt de `hanabi-dwh/`. L'API se contente d'un
`SELECT ... LIMIT`, ce qui explique qu'une vue de l'entrepot reponde en quelques
millisecondes la ou la meme question posee a `analytics.py` demande plusieurs
agregations sur la table des commandes.

Les deux chemins coexistent a dessein, et ne racontent pas la meme histoire :

- `analytics.py` lit la base transactionnelle. Ses chiffres sont ceux de
  l'instant, au prix d'un recalcul a chaque affichage ;
- l'entrepot lit un instantane, date par `gold.gold_execution`. Ses chiffres
  sont ceux de la derniere construction, et ne bougent pas entre deux.

Un entrepot construit par lots est toujours en retard sur la base ; le probleme
n'est pas ce retard mais de ne pas savoir de combien, d'ou l'horodatage affiche
partout dans l'interface.

Sur SQLite - la base de developpement et celle de la suite de tests - ce schema
n'existe pas : le SQL de l'entrepot emploie `date_trunc`, `generate_series` et
des fonctions de fenetrage. Toutes les fonctions ci-dessous le detectent et
rendent un etat « entrepot absent » plutot que de lever une erreur. C'est un
etat normal, pas une panne, et l'interface le presente comme tel.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

SCHEMA = "gold"

# Plafond de lignes rendues en une fois. `gold_clients_rfm` compte une ligne par
# client acheteur - plusieurs dizaines de milliers - et les servir toutes ferait
# un corps de reponse de plusieurs mega-octets pour un tableau qui en affiche
# vingt-cinq.
LIMITE_MAX = 200
LIMITE_DEFAUT = 25

# Un identifiant SQL valide dans ce projet. Les noms interpoles dans les
# requetes viennent tous soit du registre ci-dessous, soit de
# `information_schema` : ils ne peuvent donc pas etre choisis par un appelant.
# Cette verification est la ceinture qui accompagne les bretelles - le jour ou
# quelqu'un elargira le registre sans y penser, elle sera encore la.
_IDENTIFIANT = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Mart:
    """Une table d'agregats exposee au back-office.

    `question` compte autant que le reste : une table d'entrepot sans la
    question a laquelle elle repond est un tableau de nombres, et personne ne
    sait quoi en faire. C'est ce texte que l'interface affiche au-dessus du
    resultat.
    """

    cle: str
    table: str
    titre: str
    question: str
    # Tri applique par defaut, ecrit directement en SQL parce qu'il porte
    # parfois sur deux colonnes. Valeur de code, jamais d'appelant : c'est ce
    # qui autorise a l'interpoler telle quelle dans la requete.
    tri: str


# Ordre d'affichage volontaire, du general au particulier : la serie mensuelle
# d'abord, parce que c'est la vue qu'on ouvre en premier, les regles
# d'association en dernier, parce qu'on y va en connaissance de cause.
MARTS: tuple[Mart, ...] = (
    Mart(
        cle="kpi_mensuel",
        table="gold_kpi_mensuel",
        titre="Indicateurs mensuels",
        question="Comment le chiffre d'affaires, la marge et l'audience evoluent-ils mois par mois ?",
        tri="mois_date desc",
    ),
    Mart(
        cle="performance_produit",
        table="gold_performance_produit",
        titre="Performance par produit",
        question="Quelles references rapportent, lesquelles font du volume sans marge ?",
        tri="marge_cents desc",
    ),
    Mart(
        cle="performance_categorie",
        table="gold_performance_categorie",
        titre="Performance par categorie",
        question="Quelle famille du catalogue porte reellement le resultat ?",
        tri="ca_cents desc",
    ),
    Mart(
        cle="segments_rfm",
        table="gold_segments_rfm",
        titre="Segments RFM",
        question="Comment la clientele se repartit-elle, et quelle part du chiffre chaque segment pese-t-il ?",
        tri="rang asc",
    ),
    Mart(
        cle="clients_rfm",
        table="gold_clients_rfm",
        titre="Clients notes RFM",
        question="Qui sont les clients derriere chaque segment, et lesquels relancer ?",
        tri="montant_cents desc",
    ),
    Mart(
        cle="cohortes",
        table="gold_cohortes_retention",
        titre="Retention par cohorte",
        question="Les clients recrutes un mois donne reviennent-ils les mois suivants ?",
        tri="cohorte_date desc, decalage_mois asc",
    ),
    Mart(
        cle="demographie",
        table="gold_demographie_clients",
        titre="Demographie et achat",
        question="Ville, age, civilite : quels profils achetent, et pour combien ?",
        tri="ca_cents desc",
    ),
    Mart(
        cle="promotions",
        table="gold_promotions",
        titre="Codes promotionnels",
        question="Quels codes font entrer du chiffre, et lesquels n'ont jamais servi ?",
        tri="ca_cents desc",
    ),
    Mart(
        cle="affinites",
        table="gold_affinites_produits",
        titre="Affinites entre produits",
        question="Quels articles s'achetent ensemble plus souvent que le hasard ne le voudrait ?",
        tri="lift desc",
    ),
)

PAR_CLE = {mart.cle: mart for mart in MARTS}


# Le graphe du projet dbt, decrit ici pour que l'interface puisse le dessiner.
#
# Redit volontairement ce que `hanabi-dwh/models/` contient : l'API n'a pas
# acces au projet dbt, qui n'est pas deploye avec elle. La duplication est
# assumee et bornee - elle ne porte que des noms, jamais une regle de calcul, et
# une divergence se voit immediatement puisque l'interface signale les modeles
# annonces qu'elle ne trouve pas en base.
COUCHES = (
    {
        "cle": "bronze",
        "titre": "Bronze",
        "resume": "Les tables de l'application, nommees sous une forme stable. Aucune transformation.",
        "materialisation": "vues",
        "modeles": [
            "brz_clients", "brz_produits", "brz_commandes", "brz_lignes_commande",
            "brz_vues_produit", "brz_avis", "brz_promos",
        ],
    },
    {
        "cle": "silver",
        "titre": "Silver",
        "resume": "Donnees nettoyees et conformees. Les regles metier sont ecrites ici, une seule fois.",
        "materialisation": "vues, sauf la table de faits",
        "modeles": [
            "slv_clients", "slv_commandes", "slv_lignes_commande",
            "slv_vues_produit", "slv_avis", "slv_calendrier_mensuel",
        ],
    },
    {
        "cle": "gold",
        "titre": "Gold",
        "resume": "Une table d'agregats par question metier. C'est la seule couche que ce tableau lit.",
        "materialisation": "tables",
        "modeles": [mart.table for mart in MARTS] + ["gold_execution"],
    },
)


def _est_postgres(db: Session) -> bool:
    """Vrai si la session parle a PostgreSQL.

    L'entrepot n'existe que la. Poser la question au dialecte plutot que de
    tenter la requete et rattraper l'erreur evite de polluer les journaux d'une
    exception attendue a chaque appel en developpement.
    """
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _tables_presentes(db: Session, schemas: tuple[str, ...]) -> set[str]:
    lignes = db.execute(
        text(
            "select table_schema, table_name from information_schema.tables "
            "where table_schema = any(:schemas)"
        ),
        {"schemas": list(schemas)},
    ).all()
    return {f"{schema}.{table}" for schema, table in lignes}


def _format_colonne(nom: str, type_sql: str) -> str:
    """Devine comment presenter une colonne, d'apres son nom et son type.

    Le nommage de l'entrepot est regulier - `_cents` pour un montant, `taux_` ou
    `part_` pour une proportion, `_le` pour un horodatage - et cette regularite
    suffit a decider du formatage. L'alternative aurait ete de decrire une
    centaine de colonnes a la main dans le registre ci-dessus : une liste que
    personne ne tient a jour, et qui se serait desynchronisee au premier modele
    modifie.

    En cas de doute, on rend `texte` : afficher un nombre brut est moins grave
    que de l'afficher en euros alors qu'il n'en est pas.
    """
    if nom == "id" or nom.endswith("_id"):
        # Un identifiant est un nombre par accident, pas par nature : l'afficher
        # « 66 164 » avec un separateur de milliers invite a le lire comme une
        # quantite, et empeche de le recopier tel quel dans une requete.
        return "identifiant"
    if nom.endswith("_cents"):
        return "euro"
    if nom.startswith(("taux_", "part_")) or nom in ("support", "confiance_ab", "confiance_ba"):
        return "pourcent"
    if type_sql in ("boolean",):
        return "booleen"
    if type_sql in ("date", "timestamp with time zone", "timestamp without time zone"):
        return "date"
    if type_sql in ("integer", "bigint", "smallint"):
        return "entier"
    if type_sql in ("numeric", "double precision", "real"):
        return "decimal"
    return "texte"


def _libelle_colonne(nom: str) -> str:
    """Intitule lisible pour un en-tete de tableau.

    Le suffixe `_cents` disparait : la valeur est deja rendue en euros a
    l'affichage, et une colonne intitulee « Ca cents » affichant « 4 144,92 € »
    serait une contradiction sous les yeux du lecteur.
    """
    base = nom[: -len("_cents")] if nom.endswith("_cents") else nom
    return base.replace("_", " ").capitalize()


def _valeur_json(valeur):
    """Ramene une valeur PostgreSQL a un type que FastAPI sait serialiser.

    `numeric` remonte en `Decimal`, que le serialiseur JSON refuse. On passe par
    `float` : l'entrepot ne rend en `numeric` que des taux et des moyennes, ou
    la precision decimale exacte n'a aucun enjeu. Les montants, eux, sont des
    entiers de centimes et ne passent jamais par ici.
    """
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    return valeur


def _colonnes(db: Session, table: str) -> list[dict]:
    lignes = db.execute(
        text(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = :schema and table_name = :table "
            "order by ordinal_position"
        ),
        {"schema": SCHEMA, "table": table},
    ).all()
    return [
        {
            "nom": nom,
            "libelle": _libelle_colonne(nom),
            "format": _format_colonne(nom, type_sql),
        }
        for nom, type_sql in lignes
    ]


def etat(db: Session) -> dict:
    """Ce que l'interface a besoin de savoir avant d'afficher quoi que ce soit.

    Rend toujours une reponse, meme sans entrepot : `disponible` a faux et la
    marche a suivre pour le construire. Une route qui repondrait 503 obligerait
    l'interface a traiter un cas d'erreur pour ce qui est un etat parfaitement
    normal en developpement.
    """
    if not _est_postgres(db):
        return {
            "disponible": False,
            "raison": "moteur",
            "construit_le": None,
            "couches": [dict(couche, presents=[]) for couche in COUCHES],
            "marts": [],
        }

    presentes = _tables_presentes(db, ("bronze", "silver", SCHEMA))

    couches = [
        dict(
            couche,
            presents=[
                modele for modele in couche["modeles"]
                if f"{couche['cle']}.{modele}" in presentes
            ],
        )
        for couche in COUCHES
    ]

    construit_le = None
    invocation = None
    if f"{SCHEMA}.gold_execution" in presentes:
        ligne = db.execute(
            text(f"select construit_le, invocation_id from {SCHEMA}.gold_execution limit 1")
        ).first()
        if ligne:
            construit_le = ligne[0].isoformat() if ligne[0] else None
            invocation = ligne[1]

    marts = []
    for mart in MARTS:
        existe = f"{SCHEMA}.{mart.table}" in presentes
        marts.append({
            "cle": mart.cle,
            "table": f"{SCHEMA}.{mart.table}",
            "titre": mart.titre,
            "question": mart.question,
            "disponible": existe,
            # Comptage exact plutot qu'estime : les tables comptent au plus
            # quelques dizaines de milliers de lignes, et `reltuples` renvoie
            # zero tant qu'aucun ANALYZE n'est passe - un « 0 ligne » affiche
            # sous une table pleine ferait croire a une construction ratee.
            "lignes": (
                db.execute(text(f"select count(*) from {SCHEMA}.{mart.table}")).scalar() or 0
                if existe else 0
            ),
        })

    return {
        "disponible": any(m["disponible"] for m in marts),
        "raison": None if any(m["disponible"] for m in marts) else "non_construit",
        "construit_le": construit_le,
        "invocation": invocation,
        "couches": couches,
        "marts": marts,
    }


class EntrepotAbsent(RuntimeError):
    """L'entrepot n'a pas ete construit sur cette base."""


class MartInconnu(KeyError):
    """Cle demandee absente du registre."""


def interroger(
    db: Session,
    cle: str,
    *,
    limite: int = LIMITE_DEFAUT,
    decalage: int = 0,
    tri: str | None = None,
    sens: str = "desc",
) -> dict:
    """Rend le contenu d'une table d'agregats, et le SQL qui l'a produit.

    Le SQL accompagne le resultat a dessein. Un tableau de bord qui affiche des
    nombres sans dire d'ou ils viennent demande qu'on lui fasse confiance ;
    celui-ci montre la requete, que l'on peut rejouer telle quelle dans
    n'importe quel client PostgreSQL pour verifier.

    Aucune portion de la requete ne vient de l'appelant. Le nom de table est lu
    dans le registre, la colonne de tri est verifiee contre le schema reel de la
    table, le sens est ramene a `asc` ou `desc`, et les bornes sont des
    parametres lies. C'est ce qui permet d'exposer une lecture SQL sans ouvrir
    une injection.
    """
    mart = PAR_CLE.get(cle)
    if mart is None:
        raise MartInconnu(cle)
    if not _est_postgres(db):
        raise EntrepotAbsent(cle)

    colonnes = _colonnes(db, mart.table)
    if not colonnes:
        raise EntrepotAbsent(cle)

    noms = {colonne["nom"] for colonne in colonnes}
    if tri and tri in noms and _IDENTIFIANT.match(tri):
        ordre = f"{tri} {'asc' if sens == 'asc' else 'desc'}"
        # Les NULL en dernier quel que soit le sens : sur ces tables, un NULL
        # signifie « pas mesurable » (une couverture de stock infinie, un panier
        # moyen sans commande). Les remonter en tete d'un tri decroissant
        # placerait l'absence de mesure au-dessus du meilleur resultat.
        ordre += " nulls last"
    else:
        # Tri par defaut du registre. Interpole tel quel, ce qui est sans
        # risque : il vient du code, pas de la requete HTTP.
        ordre = mart.tri

    limite = max(1, min(int(limite), LIMITE_MAX))
    decalage = max(0, int(decalage))

    sql = (
        f"select *\n"
        f"from {SCHEMA}.{mart.table}\n"
        f"order by {ordre}\n"
        f"limit {limite} offset {decalage}"
    )

    lignes = db.execute(
        text(f"select * from {SCHEMA}.{mart.table} order by {ordre} limit :limite offset :decalage"),
        {"limite": limite, "decalage": decalage},
    ).all()
    total = db.execute(text(f"select count(*) from {SCHEMA}.{mart.table}")).scalar() or 0

    return {
        "cle": mart.cle,
        "titre": mart.titre,
        "question": mart.question,
        "table": f"{SCHEMA}.{mart.table}",
        "sql": sql,
        "colonnes": colonnes,
        "lignes": [[_valeur_json(valeur) for valeur in ligne] for ligne in lignes],
        "total": int(total),
        "limite": limite,
        "decalage": decalage,
        "tri": tri if tri in noms else None,
        "sens": sens if sens in ("asc", "desc") else "desc",
    }


# ------------------------------------------------------------------ #
# Console SQL                                                         #
# ------------------------------------------------------------------ #
#
# Ouvrir une saisie SQL libre dans une interface web est une decision qui se
# pese : c'est la porte par laquelle on lit ce qu'on ne devrait pas, ou par
# laquelle on met une base a genoux. Elle est ouverte ici parce qu'un entrepot
# qu'on ne peut pas interroger soi-meme n'est qu'un tableau de bord de plus, et
# refermee par quatre barrieres independantes - aucune n'est le seul rempart.
#
# 1. La transaction est declaree en LECTURE SEULE. C'est PostgreSQL qui refuse
#    alors toute ecriture, quelle que soit la requete : c'est la seule barriere
#    qui ne depende pas de notre capacite a analyser du SQL, et donc la seule a
#    laquelle on fait vraiment confiance.
# 2. Un delai maximal d'execution est pose. Une jointure malheureuse sur les
#    sept cent mille consultations de fiche est interrompue par le serveur au
#    lieu de bloquer une connexion du pool.
# 3. Les tables reellement lues sont demandees au PLANIFICATEUR, via EXPLAIN,
#    et non devinees par une expression reguliere. Une requete qui atteint
#    `public.users` par une CTE, une sous-requete ou une vue est refusee, la ou
#    un filtre sur le texte de la requete se laisserait contourner.
# 4. La forme est verifiee avant tout : une seule instruction, commencant par
#    SELECT ou WITH, sans mot-clef d'ecriture.
#
# Ce qui reste possible : lire l'entrepot en entier. C'est voulu - il ne
# contient aucun secret, le condensat des mots de passe n'entre jamais en
# bronze, et les donnees sont fictives.

# Schemas ouverts a la lecture. `public` en est absent : c'est la que vivent les
# condensats de mots de passe, et l'entrepot expose deja tout ce qui a un usage
# analytique.
SCHEMAS_AUTORISES = frozenset({"bronze", "silver", "gold"})

# Delai au-dela duquel PostgreSQL interrompt la requete. Cinq secondes suffisent
# tres largement a l'entrepot ; au-dela, c'est que la requete part en vrille.
DELAI_MAX_MS = 5000

LIMITE_SQL_MAX = 500
LIMITE_SQL_DEFAUT = 50

# Mots-clefs d'ecriture ou d'administration. La transaction en lecture seule les
# rejetterait de toute facon ; les attraper ici permet de rendre un message qui
# dit quoi corriger, plutot qu'une erreur de PostgreSQL en anglais.
_MOTS_INTERDITS = (
    "insert", "update", "delete", "merge", "truncate", "drop", "alter", "create",
    "grant", "revoke", "comment", "copy", "vacuum", "analyze", "reindex", "cluster",
    "call", "do", "set", "reset", "begin", "commit", "rollback", "savepoint",
    "listen", "notify", "lock", "prepare", "execute", "deallocate", "refresh",
)

_DEBUT_VALIDE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class SqlRefuse(ValueError):
    """La requete n'a pas passe une des barrieres. Le message est destine a l'ecran."""


def _sans_litteraux(requete: str) -> str:
    """Retire commentaires et chaines, pour chercher des mots-clefs sans faux positifs.

    Sans cela, `select nom from gold.gold_clients_rfm where nom = 'Delete'`
    serait refusee pour un mot present dans une donnee, et `-- update` en
    commentaire ferait de meme. On ne cherche des mots-clefs que dans ce qui en
    est reellement.
    """
    sans_bloc = re.sub(r"/\*.*?\*/", " ", requete, flags=re.DOTALL)
    sans_ligne = re.sub(r"--[^\n]*", " ", sans_bloc)
    sans_texte = re.sub(r"'(?:[^']|'')*'", " ", sans_ligne)
    return re.sub(r'"[^"]*"', " ", sans_texte)


def _valide_la_forme(requete: str) -> str:
    """Premiere barriere : la requete doit etre une lecture unique."""
    nettoyee = requete.strip().rstrip(";").strip()
    if not nettoyee:
        raise SqlRefuse("Requete vide.")

    if not _DEBUT_VALIDE.match(nettoyee):
        raise SqlRefuse(
            "Seules les lectures sont acceptees : la requete doit commencer par "
            "SELECT ou WITH."
        )

    analysable = _sans_litteraux(nettoyee)

    # Une instruction et une seule. Le point-virgule final a deja ete retire ;
    # tout autre separe deux instructions, et la seconde echapperait a l'examen
    # du planificateur fait sur la premiere.
    if ";" in analysable:
        raise SqlRefuse(
            "Une seule instruction a la fois : retire le point-virgule qui en separe deux."
        )

    for mot in _MOTS_INTERDITS:
        if re.search(rf"\b{mot}\b", analysable, re.IGNORECASE):
            raise SqlRefuse(
                f"Mot-clef « {mot.upper()} » refuse : cette console est en lecture seule."
            )

    return nettoyee


def _relations_du_plan(plan) -> set[tuple[str, str]]:
    """Parcourt le plan rendu par EXPLAIN et releve chaque table lue.

    Le plan est un arbre de dictionnaires imbriques dont la forme varie selon
    les noeuds ; on le traverse entierement plutot que d'en supposer la
    structure, et on releve les couples (schema, table) partout ou ils
    apparaissent.
    """
    trouvees: set[tuple[str, str]] = set()

    def visite(noeud):
        if isinstance(noeud, dict):
            if "Relation Name" in noeud:
                trouvees.add((noeud.get("Schema") or "?", noeud["Relation Name"]))
            for valeur in noeud.values():
                visite(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                visite(valeur)

    visite(plan)
    return trouvees


def executer_sql(db: Session, requete: str, limite: int = LIMITE_SQL_DEFAUT) -> dict:
    """Execute une lecture libre sur l'entrepot, et rend son resultat.

    Le SQL de l'appelant n'est jamais interpole dans une autre requete : il est
    envoye tel quel, et c'est la transaction en lecture seule qui le contient.
    L'enveloppe `select * from ( ... ) limit n` est la seule reecriture, et elle
    ne peut pas changer le sens d'une lecture.
    """
    if not _est_postgres(db):
        raise EntrepotAbsent("sql")

    nettoyee = _valide_la_forme(requete)
    limite = max(1, min(int(limite), LIMITE_SQL_MAX))

    try:
        # Toute transaction implicite en cours est refermee : `SET TRANSACTION`
        # doit etre la premiere instruction de la sienne, sans quoi PostgreSQL
        # la refuse.
        db.rollback()
        db.execute(text("set transaction read only"))
        db.execute(text(f"set local statement_timeout = {DELAI_MAX_MS}"))

        # EXPLAIN valide la syntaxe ET revele les tables, sans executer quoi que
        # ce soit. Deux barrieres pour le prix d'une : une requete mal ecrite
        # echoue ici, avant d'avoir touche la moindre donnee.
        try:
            plan = db.execute(text(f"explain (format json, verbose) {nettoyee}")).scalar()
        except SQLAlchemyError as erreur:
            raise SqlRefuse(_message_postgres(erreur)) from erreur

        relations = _relations_du_plan(plan)
        interdites = sorted(
            f"{schema}.{table}"
            for schema, table in relations
            if schema not in SCHEMAS_AUTORISES
        )
        if interdites:
            raise SqlRefuse(
                "Lecture refusee sur : " + ", ".join(interdites) + ". "
                "Cette console n'ouvre que les schemas "
                + ", ".join(sorted(SCHEMAS_AUTORISES)) + "."
            )

        enveloppe = f"select * from (\n{nettoyee}\n) as resultat limit :limite"
        try:
            resultat = db.execute(text(enveloppe), {"limite": limite})
            colonnes_brutes = list(resultat.keys())
            lignes = resultat.fetchall()
        except SQLAlchemyError as erreur:
            raise SqlRefuse(_message_postgres(erreur)) from erreur

    finally:
        # Rien n'a ete ecrit - la transaction est en lecture seule - mais on la
        # referme explicitement pour rendre la connexion au pool dans un etat
        # propre, et pour que le `statement_timeout` local ne survive pas.
        db.rollback()

    colonnes = [
        {
            "nom": nom,
            "libelle": _libelle_colonne(nom),
            # Le type reel n'est pas connu ici - le resultat peut etre une
            # expression calculee, sans table d'origine. On se rabat sur le nom,
            # qui suffit dans un entrepot ou le nommage est regulier.
            "format": _format_colonne(nom, _type_devine(lignes, index)),
        }
        for index, nom in enumerate(colonnes_brutes)
    ]

    return {
        "sql": nettoyee,
        "colonnes": colonnes,
        "lignes": [[_valeur_json(valeur) for valeur in ligne] for ligne in lignes],
        "total": len(lignes),
        "limite": limite,
        "tronque": len(lignes) >= limite,
        "tables_lues": sorted(f"{schema}.{table}" for schema, table in relations),
    }


def _type_devine(lignes, index: int) -> str:
    """Type SQL approche d'une colonne de resultat, deduit de sa premiere valeur.

    Le curseur ne rend pas le type des colonnes d'une expression calculee. Plutot
    que de tout afficher en texte, on regarde la premiere valeur non nulle : cela
    suffit a distinguer un entier d'un decimal, ce dont le formatage a besoin.
    """
    for ligne in lignes:
        valeur = ligne[index]
        if valeur is None:
            continue
        if isinstance(valeur, bool):
            return "boolean"
        if isinstance(valeur, int):
            return "bigint"
        if isinstance(valeur, (Decimal, float)):
            return "numeric"
        if isinstance(valeur, (datetime, date)):
            return "date"
        return "text"
    return "text"


def _message_postgres(erreur: Exception) -> str:
    """Ramene une erreur SQLAlchemy a la ligne que PostgreSQL a reellement dite.

    L'exception complete embarque la requete et la trace du pilote, illisibles
    dans une interface. La premiere ligne du message d'origine est celle qui dit
    quoi corriger.
    """
    origine = getattr(erreur, "orig", None) or erreur
    premiere = str(origine).strip().split("\n")[0]
    if "statement timeout" in premiere.lower():
        return (
            f"Requete interrompue apres {DELAI_MAX_MS // 1000} s. "
            "Ajoute un filtre ou une limite : la table des consultations compte "
            "plusieurs centaines de milliers de lignes."
        )
    return premiere or "Requete refusee par la base."
