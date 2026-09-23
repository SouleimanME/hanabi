# -*- coding: utf-8 -*-
"""Contrôles de volume et de fraîcheur, joués après la construction.

Les tests dbt vérifient la forme des données (clés, valeurs admises,
rapprochements). Ces contrôles vérifient qu'elles arrivent et ne disparaissent
pas. L'instance Dagster de GitHub Actions est jetable : chaque résultat est
aussi consigné dans `controles.journal`, que lit le back-office.

Pour accepter une baisse voulue du nombre de commandes (base remise à zéro),
effacer l'historique du contrôle :
    delete from controles.journal where controle = 'commandes_jamais_en_baisse';
"""

import datetime as dt
from dataclasses import dataclass

import dagster as dg
import psycopg

# Import direct, sans `from __future__ import annotations` (voir actifs_dbt.py)
from dagster import AssetCheckExecutionContext
from dagster_dbt import get_asset_key_for_model

from ingestion.sources import url_base

from .actifs_dbt import actifs_dbt

# Une vente tous les trois jours au moins ; la BCE ne cote ni le week-end ni ses
# fériés, et Noël plus un week-end font quatre jours sans cotation
DELAI_VENTE_JOURS = 3
DELAI_TAUX_JOURS = 5

DDL = """
create schema if not exists controles;

create table if not exists controles.journal (
    id          bigserial   primary key,
    execute_le  timestamptz not null default now(),
    controle    text        not null,
    titre       text        not null,
    famille     text        not null,
    severite    text        not null,
    reussi      boolean     not null,
    valeur      numeric,
    attendu     text        not null,
    message     text        not null,
    run_id      text
);

create index if not exists journal_par_controle
    on controles.journal (controle, execute_le desc);

grant usage on schema controles to public;
grant select on all tables in schema controles to public;
"""


@dataclass(frozen=True)
class Verdict:
    """Résultat d'un contrôle, dans les termes du journal."""

    reussi: bool
    valeur: float | None
    attendu: str
    message: str


def _jours(n: int) -> str:
    return f"{n} jour" if n == 1 else f"{n} jours"


# Mêmes abréviations que les dates du back-office
_MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def _date(jour: dt.date) -> str:
    return f"{jour.day} {_MOIS[jour.month - 1]} {jour.year}"


def _nombre(n: int) -> str:
    """Milliers séparés par une espace fine insécable, comme dans le back-office."""
    return f"{n:,}".replace(",", " ")


def juge_commandes(actuel: int, plus_haut: int | None) -> Verdict:
    """Une commande n'est jamais supprimée : l'effacement RGPD l'anonymise."""
    if plus_haut is None:
        return Verdict(
            True, actuel, "aucune référence", f"Première mesure : {_nombre(actuel)} commandes."
        )
    if actuel >= plus_haut:
        return Verdict(True, actuel, f"au moins {_nombre(plus_haut)}", f"{_nombre(actuel)} commandes.")
    return Verdict(
        False,
        actuel,
        f"au moins {_nombre(plus_haut)}",
        f"{_nombre(plus_haut - actuel)} commandes ont disparu depuis le plus haut relevé "
        f"({_nombre(plus_haut)}).",
    )


def juge_calendrier(
    lignes: int, premier: dt.date | None, dernier: dt.date | None, aujourdhui: dt.date
) -> Verdict:
    """Une ligne par jour, sans trou, jusqu'à aujourd'hui."""
    if not lignes or premier is None or dernier is None:
        return Verdict(False, 0, "une ligne par jour", "La table est vide.")
    attendues = (dernier - premier).days + 1
    if lignes != attendues:
        return Verdict(
            False,
            lignes,
            f"{_nombre(attendues)} lignes",
            f"{_jours(attendues - lignes)} sans ligne entre le {_date(premier)} et le {_date(dernier)}.",
        )
    if dernier != aujourdhui:
        return Verdict(
            False,
            lignes,
            f"jusqu'au {_date(aujourdhui)}",
            f"La série s'arrête le {_date(dernier)}.",
        )
    return Verdict(
        True,
        lignes,
        f"{_nombre(attendues)} lignes",
        f"Du {_date(premier)} au {_date(dernier)}, sans trou.",
    )


def juge_fraicheur(
    dernier: dt.date | None, aujourdhui: dt.date, delai: int, quoi: str
) -> Verdict:
    """Âge de la donnée la plus récente, en jours."""
    attendu = f"{_jours(delai)} au plus"
    if dernier is None:
        return Verdict(False, None, attendu, f"Aucune {quoi} en base.")
    age = (aujourdhui - dernier).days
    if age <= delai:
        quand = "aujourd'hui" if age == 0 else f"il y a {_jours(age)}"
        return Verdict(True, age, attendu, f"Dernière {quoi} {quand}, le {_date(dernier)}.")
    return Verdict(
        False, age, attendu, f"Aucune {quoi} depuis le {_date(dernier)}, il y a {_jours(age)}."
    )


def _cle(modele: str) -> dg.AssetKey:
    return get_asset_key_for_model([actifs_dbt], modele)


# Nom, titre affiché, famille, modèle rattaché, gravité
CONTROLES = (
    ("commandes_jamais_en_baisse", "Commandes jamais en baisse", "volume", "slv_commandes", "erreur"),
    ("un_jour_par_jour", "Un jour par jour", "volume", "gold_ca_quotidien", "erreur"),
    ("derniere_vente", "Dernière vente", "fraicheur", "gold_ca_quotidien", "alerte"),
    ("dernier_taux", "Dernier taux de change", "fraicheur", "brz_taux_change", "alerte"),
)

GRAVITES = {"erreur": dg.AssetCheckSeverity.ERROR, "alerte": dg.AssetCheckSeverity.WARN}


@dg.multi_asset_check(
    specs=[
        dg.AssetCheckSpec(
            name=nom,
            asset=_cle(modele),
            description=titre,
            # Un échec bloquant fait échouer l'exécution : le workflow passe au rouge
            blocking=gravite == "erreur",
        )
        for nom, titre, _famille, modele, gravite in CONTROLES
    ],
    name="controles_volume_fraicheur",
)
def controles_volume_fraicheur(context: AssetCheckExecutionContext):
    with psycopg.connect(url_base(), autocommit=True) as cx, cx.cursor() as c:
        c.execute(DDL)
        c.execute("select current_date")
        aujourdhui = c.fetchone()[0]

        c.execute("select count(*) from silver.slv_commandes")
        commandes = c.fetchone()[0]
        c.execute(
            "select max(valeur) from controles.journal where controle = 'commandes_jamais_en_baisse'"
        )
        plus_haut = c.fetchone()[0]

        c.execute("select count(*), min(jour), max(jour) from gold.gold_ca_quotidien")
        lignes, premier, dernier = c.fetchone()
        c.execute("select max(jour) from gold.gold_ca_quotidien where commandes > 0")
        derniere_vente = c.fetchone()[0]
        c.execute("select max(jour) from externe.taux_change")
        dernier_taux = c.fetchone()[0]

        verdicts = {
            "commandes_jamais_en_baisse": juge_commandes(
                commandes, int(plus_haut) if plus_haut is not None else None
            ),
            "un_jour_par_jour": juge_calendrier(lignes, premier, dernier, aujourdhui),
            "derniere_vente": juge_fraicheur(derniere_vente, aujourdhui, DELAI_VENTE_JOURS, "vente"),
            "dernier_taux": juge_fraicheur(dernier_taux, aujourdhui, DELAI_TAUX_JOURS, "cotation"),
        }

        for nom, titre, famille, modele, gravite in CONTROLES:
            v = verdicts[nom]
            c.execute(
                """insert into controles.journal
                       (controle, titre, famille, severite, reussi, valeur, attendu, message, run_id)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (nom, titre, famille, gravite, v.reussi, v.valeur, v.attendu, v.message, context.run.run_id),
            )
            yield dg.AssetCheckResult(
                check_name=nom,
                asset_key=_cle(modele),
                passed=v.reussi,
                severity=GRAVITES[gravite],
                description=v.message,
                metadata={"attendu": v.attendu}
                | ({"valeur": v.valeur} if v.valeur is not None else {}),
            )
