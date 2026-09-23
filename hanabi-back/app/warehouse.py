# -*- coding: utf-8 -*-
"""Lecture des tables d'agrégats construites par dbt (schéma `gold`).

Ce module ne calcule rien : `analytics.py` lit la base transactionnelle à
l'instant, l'entrepôt lit un instantané daté par `gold.gold_execution`.

Sur SQLite (développement, tests), l'entrepôt n'existe pas : ses modèles
emploient `date_trunc`, `generate_series` et des fenêtres. Les fonctions
ci-dessous rendent alors un état « absent » au lieu de lever une erreur.
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

# `gold_clients_rfm` compte une ligne par client acheteur
LIMITE_MAX = 200
LIMITE_DEFAUT = 25

# Les noms interpolés viennent du registre ou d'information_schema, jamais de
# l'appelant ; la vérification reste en place si le registre s'élargit.
_IDENTIFIANT = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Mart:
    """Une table d'agrégats exposée au back-office, avec la question qu'elle traite."""

    cle: str
    table: str
    titre: str
    question: str
    # Tri par défaut, en SQL littéral (parfois sur deux colonnes). Valeur de code uniquement.
    tri: str


MARTS: tuple[Mart, ...] = (
    Mart(
        cle="ca_quotidien",
        table="gold_ca_quotidien",
        titre="Chiffre d'affaires quotidien",
        question=(
            "Une journée faible est-elle un incident ou un jour férié, et la marge "
            "bouge-t-elle à cause des prix ou du yen ?"
        ),
        tri="jour desc",
    ),
    Mart(
        cle="kpi_mensuel",
        table="gold_kpi_mensuel",
        titre="Indicateurs mensuels",
        question="Comment le chiffre d'affaires, la marge et l'audience évoluent-ils mois par mois ?",
        tri="mois_date desc",
    ),
    Mart(
        cle="performance_produit",
        table="gold_performance_produit",
        titre="Performance par produit",
        question="Quelles références rapportent, lesquelles font du volume sans marge ?",
        tri="marge_cents desc",
    ),
    Mart(
        cle="performance_categorie",
        table="gold_performance_categorie",
        titre="Performance par catégorie",
        question="Quelle famille du catalogue porte réellement le résultat ?",
        tri="ca_cents desc",
    ),
    Mart(
        cle="segments_rfm",
        table="gold_segments_rfm",
        titre="Segments RFM",
        question="Comment la clientèle se répartit-elle, et quelle part du chiffre pèse chaque segment ?",
        tri="rang asc",
    ),
    Mart(
        cle="clients_rfm",
        table="gold_clients_rfm",
        titre="Clients notés RFM",
        question="Qui sont les clients derrière chaque segment, et lesquels relancer ?",
        tri="montant_cents desc",
    ),
    Mart(
        cle="cohortes",
        table="gold_cohortes_retention",
        titre="Rétention par cohorte",
        question="Les clients recrutés un mois donné reviennent-ils les mois suivants ?",
        tri="cohorte_date desc, decalage_mois asc",
    ),
    Mart(
        cle="demographie",
        table="gold_demographie_clients",
        titre="Démographie et achat",
        question="Ville, âge, civilité : quels profils achètent, et pour combien ?",
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
        titre="Affinités entre produits",
        question="Quels articles s'achètent ensemble plus souvent que le hasard ?",
        tri="lift desc",
    ),
)

PAR_CLE = {mart.cle: mart for mart in MARTS}


# Copie des noms de modèles de `hanabi-dwh/models/`, que l'API ne déploie pas.
# Tout modèle ajouté là-bas doit l'être ici : test_les_couches_decrivent_tous_les_modeles_dbt.
COUCHES = (
    {
        "cle": "bronze",
        "titre": "Bronze",
        "resume": "Tables de l'application et sources externes, renommées sous une forme stable. Aucune transformation.",
        "materialisation": "vues",
        "modeles": [
            "brz_clients", "brz_produits", "brz_commandes", "brz_lignes_commande",
            "brz_vues_produit", "brz_avis", "brz_promos",
            "brz_taux_change", "brz_jours_feries",
        ],
    },
    {
        "cle": "silver",
        "titre": "Silver",
        "resume": "Données nettoyées et conformées. Les règles métier s'écrivent ici, une seule fois.",
        "materialisation": "vues, sauf la table de faits",
        "modeles": [
            "slv_clients", "slv_commandes", "slv_lignes_commande",
            "slv_vues_produit", "slv_avis", "slv_calendrier_mensuel",
            "slv_calendrier_quotidien",
        ],
    },
    {
        "cle": "gold",
        "titre": "Gold",
        "resume": "Une table d'agrégats par question métier. Seule couche lue par cet écran.",
        "materialisation": "tables",
        "modeles": [mart.table for mart in MARTS] + ["gold_execution"],
    },
)


def _est_postgres(db: Session) -> bool:
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
    """Format d'affichage déduit du nommage (`_cents`, `taux_`, `part_`, `_id`) et du type.

    Par défaut `texte` : un nombre brut vaut mieux qu'un faux montant.
    """
    if nom == "id" or nom.endswith("_id"):
        # Sans séparateur de milliers, pour se recopier tel quel
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


# Les noms de colonnes sont en ASCII ; l'en-tête reprend accents et sigles
_MOTS_AFFICHES = {
    "ab": "A→B", "abc": "ABC", "activite": "activité", "age": "âge", "annee": "année",
    "ba": "B→A", "ca": "CA", "categorie": "catégorie", "civilite": "civilité",
    "cout": "coût", "cumulee": "cumulée", "decalage": "décalage", "derniere": "dernière",
    "eur": "EUR", "expire": "expiré", "ferie": "férié", "feries": "fériés",
    "frequence": "fréquence", "id": "ID", "jpy": "JPY", "kpi": "KPI",
    "premiere": "première", "recence": "récence", "reference": "référence",
    "references": "références", "retention": "rétention",
    "rfm": "RFM", "unites": "unités",
}


def _libelle_colonne(nom: str) -> str:
    """En-tête lisible ; le suffixe `_cents` tombe puisque la valeur s'affiche en euros."""
    base = nom[: -len("_cents")] if nom.endswith("_cents") else nom
    mots = [_MOTS_AFFICHES.get(mot, mot) for mot in base.split("_") if mot]
    libelle = " ".join(mots)
    return libelle[:1].upper() + libelle[1:]


def _valeur_json(valeur):
    """`Decimal` en float (taux et moyennes seulement), dates en ISO 8601."""
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


def _derniers_controles(db: Session) -> list[dict]:
    """Dernier résultat de chaque contrôle Dagster, volume d'abord puis fraîcheur."""
    lignes = db.execute(
        text(
            "select distinct on (controle) controle, titre, famille, severite, reussi, "
            "valeur, attendu, message, execute_le "
            "from controles.journal order by controle, execute_le desc"
        )
    ).mappings().all()
    controles = [
        {
            "controle": ligne["controle"],
            "titre": ligne["titre"],
            "famille": ligne["famille"],
            "severite": ligne["severite"],
            "reussi": ligne["reussi"],
            "valeur": _valeur_json(ligne["valeur"]),
            "attendu": ligne["attendu"],
            "message": ligne["message"],
            "execute_le": _valeur_json(ligne["execute_le"]),
        }
        for ligne in lignes
    ]
    return sorted(controles, key=lambda c: (c["famille"] != "volume", c["titre"]))


def etat(db: Session) -> dict:
    """Couches, tables disponibles, date de construction et contrôles. Répond aussi sans entrepôt."""
    if not _est_postgres(db):
        return {
            "disponible": False,
            "raison": "moteur",
            "construit_le": None,
            "couches": [dict(couche, presents=[]) for couche in COUCHES],
            "marts": [],
            "controles": [],
        }

    presentes = _tables_presentes(db, ("bronze", "silver", SCHEMA, "controles"))

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
            # count(*) exact : reltuples vaut 0 tant qu'aucun ANALYZE n'est passé
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
        # Écrits par orchestration/controles.py ; absents tant que Dagster n'a pas tourné
        "controles": _derniers_controles(db) if "controles.journal" in presentes else [],
    }


class EntrepotAbsent(RuntimeError):
    """L'entrepôt n'a pas été construit sur cette base."""


class MartInconnu(KeyError):
    """Clé absente du registre."""


def interroger(
    db: Session,
    cle: str,
    *,
    limite: int = LIMITE_DEFAUT,
    decalage: int = 0,
    tri: str | None = None,
    sens: str = "desc",
) -> dict:
    """Contenu d'une table d'agrégats et le SQL qui le produit.

    Rien ne vient de l'appelant : table lue dans le registre, colonne de tri
    vérifiée contre le schéma réel, sens ramené à asc/desc, bornes liées.
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
        # NULL signifie « non mesurable » : toujours en dernier
        ordre = f"{tri} {'asc' if sens == 'asc' else 'desc'} nulls last"
    else:
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


# --- Console SQL ---
#
# Quatre barrières indépendantes :
# 1. transaction en lecture seule, refusée par PostgreSQL quelle que soit la requête ;
# 2. statement_timeout, pour ne pas bloquer une connexion du pool ;
# 3. tables lues relevées dans le plan (EXPLAIN), pas dans le texte : une CTE
#    ou une vue qui atteint `public` est refusée ;
# 4. forme : une instruction, SELECT ou WITH, sans mot-clé d'écriture.
# S'y ajoute la limite de débit posée sur la route.

# `public` porte les condensats de mots de passe : jamais lisible ici.
SCHEMAS_AUTORISES = frozenset({"bronze", "silver", "gold", "externe", "controles"})

# Compte de démonstration, aux identifiants publics : agrégats et sources
# externes seulement. Bronze et silver gardent une ligne par client (ville,
# année de naissance), trop proche d'une personne pour un accès public.
SCHEMAS_DEMONSTRATION = frozenset({"gold", "externe", "controles"})

DELAI_MAX_MS = 5000

LIMITE_SQL_MAX = 500
LIMITE_SQL_DEFAUT = 50

# Déjà rejetés par la transaction ; les attraper ici donne un message en français
_MOTS_INTERDITS = (
    "insert", "update", "delete", "merge", "truncate", "drop", "alter", "create",
    "grant", "revoke", "comment", "copy", "vacuum", "analyze", "reindex", "cluster",
    "call", "do", "set", "reset", "begin", "commit", "rollback", "savepoint",
    "listen", "notify", "lock", "prepare", "execute", "deallocate", "refresh",
)

_DEBUT_VALIDE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class SqlRefuse(ValueError):
    """Requête refusée ; le message s'affiche tel quel."""


def _sans_litteraux(requete: str) -> str:
    """Retire commentaires et chaînes avant la recherche de mots-clés."""
    sans_bloc = re.sub(r"/\*.*?\*/", " ", requete, flags=re.DOTALL)
    sans_ligne = re.sub(r"--[^\n]*", " ", sans_bloc)
    sans_texte = re.sub(r"'(?:[^']|'')*'", " ", sans_ligne)
    return re.sub(r'"[^"]*"', " ", sans_texte)


def _valide_la_forme(requete: str) -> str:
    nettoyee = requete.strip().rstrip(";").strip()
    if not nettoyee:
        raise SqlRefuse("Requête vide.")

    if not _DEBUT_VALIDE.match(nettoyee):
        raise SqlRefuse(
            "Lecture seule : la requête doit commencer par SELECT ou WITH."
        )

    analysable = _sans_litteraux(nettoyee)

    # Une seconde instruction échapperait à l'examen du plan
    if ";" in analysable:
        raise SqlRefuse(
            "Une seule instruction à la fois : retire le point-virgule qui en sépare deux."
        )

    for mot in _MOTS_INTERDITS:
        if re.search(rf"\b{mot}\b", analysable, re.IGNORECASE):
            raise SqlRefuse(
                f"Mot-clé {mot.upper()} refusé : cette console est en lecture seule."
            )

    return nettoyee


def _relations_du_plan(plan) -> set[tuple[str, str]]:
    """Couples (schéma, table) relevés dans tout l'arbre du plan EXPLAIN."""
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


def executer_sql(
    db: Session,
    requete: str,
    limite: int = LIMITE_SQL_DEFAUT,
    schemas: frozenset[str] = SCHEMAS_AUTORISES,
) -> dict:
    """Exécute une lecture libre sur l'entrepôt, limitée aux `schemas` donnés.

    La requête part telle quelle ; seule l'enveloppe `select * from (...) limit n`
    s'y ajoute.
    """
    if not _est_postgres(db):
        raise EntrepotAbsent("sql")

    nettoyee = _valide_la_forme(requete)
    limite = max(1, min(int(limite), LIMITE_SQL_MAX))

    try:
        # SET TRANSACTION doit ouvrir sa transaction
        db.rollback()
        db.execute(text("set transaction read only"))
        db.execute(text(f"set local statement_timeout = {DELAI_MAX_MS}"))

        # EXPLAIN valide la syntaxe et révèle les tables sans rien exécuter
        try:
            plan = db.execute(text(f"explain (format json, verbose) {nettoyee}")).scalar()
        except SQLAlchemyError as erreur:
            raise SqlRefuse(_message_postgres(erreur)) from erreur

        relations = _relations_du_plan(plan)
        interdites = sorted(
            f"{schema}.{table}"
            for schema, table in relations
            if schema not in schemas
        )
        if interdites:
            raise SqlRefuse(
                "Lecture refusée sur " + ", ".join(interdites) + ". "
                "Schémas ouverts : " + ", ".join(sorted(schemas)) + "."
            )

        enveloppe = f"select * from (\n{nettoyee}\n) as resultat limit :limite"
        try:
            resultat = db.execute(text(enveloppe), {"limite": limite})
            colonnes_brutes = list(resultat.keys())
            lignes = resultat.fetchall()
        except SQLAlchemyError as erreur:
            raise SqlRefuse(_message_postgres(erreur)) from erreur

    finally:
        # Rend la connexion propre et fait tomber le statement_timeout local
        db.rollback()

    colonnes = [
        {
            "nom": nom,
            "libelle": _libelle_colonne(nom),
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
    """Type approché d'une colonne calculée, d'après sa première valeur non nulle."""
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
    """Première ligne du message PostgreSQL, sans la requête ni la trace du pilote."""
    origine = getattr(erreur, "orig", None) or erreur
    premiere = str(origine).strip().split("\n")[0]
    if "statement timeout" in premiere.lower():
        return (
            f"Requête interrompue après {DELAI_MAX_MS // 1000} s. "
            "Ajoute un filtre ou une limite : les consultations comptent "
            "plusieurs centaines de milliers de lignes."
        )
    return premiere or "Requête refusée par la base."
