# -*- coding: utf-8 -*-
"""Les deux sources externes, en amont du graphe dbt.

`ingestion/sources.py` sait deja les charger et reste utilisable seul en ligne
de commande. Ce module ne refait pas son travail : il appelle ses fonctions et
declare ce qu'elles produisent, pour que bronze cesse de dependre d'une
extraction lancee a la main.

POURQUOI LE TAUX EST PARTITIONNE ET PAS LES FERIES

Le taux de change est une serie temporelle qu'on peut vouloir rattraper : la
BCE publie chaque jour ouvre, et une extraction tombee en octobre laisse un
trou en octobre. Le decoupage en partitions mensuelles donne a Dagster de quoi
dire quels mois sont charges et lesquels manquent, et permet de rejouer une
plage sans toucher au reste. L'upsert de `charge_taux` rend l'operation sans
risque : rejouer un mois deja charge ne cree pas de doublon.

Le mois est la bonne maille, et non le jour. La source accepte une plage : un
mois coute un appel la ou trente jours en couteraient trente, pour un service
public et gratuit qu'on n'a aucune raison de marteler.

Les jours feries, eux, n'ont pas de fenetre a rattraper. Le calendrier d'une
annee entiere est publie d'un coup et ne bouge plus ; le recharger en entier
coute quatre appels. Partitionner par annee aurait produit une jolie grille et
aucun usage.
"""

import datetime as dt

import dagster as dg

# Nue, et sans `from __future__ import annotations` dans ce module : Dagster
# compare l'annotation de `context` au type reel pour decider quoi passer a la
# fonction, et une annotation differee n'est plus qu'une chaine. Meme raison
# que dans `actifs_dbt.py`.
from dagster import AssetExecutionContext

from ingestion.sources import (
    DEBUT_TAUX,
    DEVISE,
    PAYS,
    PREMIERE_ANNEE_FERIES,
    accorde_lecture,
    charge_feries,
    charge_taux,
    ouvre_base,
)

GROUPE_EXTERNE = "sources_externes"

# `end_offset=1` etend la grille au mois en cours. Sans lui, la derniere
# partition valide serait le dernier mois CLOS : le chargement quotidien
# viserait un mois qui ne bouge plus et la serie s'arreterait au 31 du mois
# precedent, sans que rien ne le signale - les jours manquants se lisent comme
# des jours non cotes, ce que la BCE produit legitimement chaque week-end.
PARTITIONS_MOIS = dg.MonthlyPartitionsDefinition(start_date=DEBUT_TAUX, end_offset=1)


@dg.asset(
    key=["externe", "taux_change"],
    group_name=GROUPE_EXTERNE,
    partitions_def=PARTITIONS_MOIS,
    kinds={"python", "postgres"},
    description=(
        "Taux de reference EUR vers JPY republies par Frankfurter (BCE). "
        "Le cout fournisseur est libelle en yen et la marge affichee en euros : "
        "la serie permet de relire cette marge a change constant, et de separer "
        "ce qui vient du prix de ce qui vient du change."
    ),
)
def taux_change(context: AssetExecutionContext) -> dg.MaterializeResult:
    fenetre = context.partition_time_window
    debut = fenetre.start.date()

    # La borne haute d'une partition est exclusive, d'ou le jour retranche. Et
    # elle est ramenee a aujourd'hui pour le mois en cours : demander des
    # cotations futures ne coute rien a la source mais ferait annoncer une
    # plage que personne n'a chargee.
    fin = min(fenetre.end.date() - dt.timedelta(days=1), dt.date.today())
    if fin < debut:
        return dg.MaterializeResult(
            metadata={"cotations": 0, "note": "partition entierement future"}
        )

    with ouvre_base() as cx:
        ecrites = charge_taux(cx, debut, fin)
        accorde_lecture(cx)

    # `ecrites` compte les lignes reellement ecrites, pas celles recues. Les
    # deux different des qu'une date revient, et c'est le chiffre de la table
    # qui interesse.
    return dg.MaterializeResult(
        metadata={
            "cotations": ecrites,
            "devise": DEVISE,
            "debut": str(debut),
            "fin": str(fin),
        }
    )


@dg.asset(
    key=["externe", "jours_feries"],
    group_name=GROUPE_EXTERNE,
    kinds={"python", "postgres"},
    description=(
        "Jours feries francais et japonais (Nager.Date). La France est le pays "
        "des clients - un ferie deplace la demande ; le Japon celui des "
        "fournisseurs - Golden Week et Obon allongent le reassort. Les "
        "confondre sous un drapeau unique melangerait deux causes opposees."
    ),
)
def jours_feries() -> dg.MaterializeResult:
    # L'annee suivante est incluse : les calendriers sont publies a l'avance, et
    # une prevision de reassort qui traverse le Nouvel An japonais a besoin de
    # savoir que les usines seront fermees.
    de = PREMIERE_ANNEE_FERIES
    a = dt.date.today().year + 1

    with ouvre_base() as cx:
        ecrits = charge_feries(cx, de, a)
        accorde_lecture(cx)

    return dg.MaterializeResult(
        metadata={
            "jours": ecrits,
            "pays": ", ".join(PAYS),
            "annees": f"{de} a {a}",
        }
    )
