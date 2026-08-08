# -*- coding: utf-8 -*-
"""Extraction des sources externes de l'entrepot.

Jusqu'ici, la chaine partait d'une base PostgreSQL et arrivait dans la meme
base : il n'y avait pas d'etape d'extraction, donc ni source qui tombe, ni
rattrapage, ni idempotence a gerer. Ce module apporte ce maillon.

DEUX SOURCES, DEUX ROLES METIER DISTINCTS

Le taux EUR/JPY. Le cout fournisseur est libelle en yen, la marge affichee en
euros. Elle n'est donc exacte qu'au taux du jour de la commande, et
`unit_cost_cents` fige cette conversion a l'achat - c'est voulu, un mois clos
ne doit pas se reecrire. Disposer de la serie permet de relire la marge a
change constant et de separer ce qui vient du prix de ce qui vient du change.

Les jours feries francais ET japonais. Les deux pays ne jouent pas le meme
role, et les confondre sous un unique drapeau « ferie » melangerait deux
causes opposees :

  - la France est le pays des CLIENTS. Un ferie deplace la demande. Un lundi
    de Pentecote a zero commande n'est pas une mauvaise journee, c'est une
    journee ferie ; sans cette colonne, la saisonnalite hebdomadaire est
    fausse et toute detection d'anomalie sonnera dans le vide.

  - le Japon est le pays des FOURNISSEURS. Golden Week fin avril, Obon en
    aout, le Nouvel An : usines et logistique a l'arret pendant plusieurs
    jours d'affilee. C'est le delai de reassort qui s'allonge, pas la
    demande qui baisse.

OU ATTERRISSENT LES DONNEES

Dans un schema `externe`, et non dans `public`. La separation est
intentionnelle : `public` appartient a l'application, qui le fait evoluer par
migrations Alembic ; `externe` appartient a la chaine de donnees. Bronze
expose ensuite les deux de la meme facon, par des vues sans transformation.

Y ecrire depuis Alembic aurait lie le cycle de vie de l'API a celui de
l'entrepot, et un `alembic downgrade` aurait pu emporter des donnees que
l'application n'a jamais produites.

IDEMPOTENCE

Chaque chargement est un `INSERT ... ON CONFLICT DO UPDATE` sur la cle
naturelle. Rejouer la meme fenetre ne cree pas de doublon et ne change rien
d'autre que `charge_le`. C'est ce qui rend le rattrapage sur, y compris apres
un echec au milieu d'une plage.

Usage :
    python -m ingestion.sources taux --depuis 2024-08-01
    python -m ingestion.sources feries --de 2024 --a 2027
    python -m ingestion.sources tout
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

import psycopg

# Frankfurter republie les taux de reference de la BCE. Sans cle, sans quota
# annonce, et l'historique remonte a 1999.
API_TAUX = "https://api.frankfurter.dev/v1"

# Nager.Date couvre une centaine de pays avec le meme schema de reponse, ce
# qui evite un analyseur par pays.
API_FERIES = "https://date.nager.at/api/v3/PublicHolidays"

DEVISE = "JPY"
PAYS = ("FR", "JP")

# La BCE ne cote pas le week-end ni ses propres feries : une plage de sept
# jours ramene cinq taux. Ce n'est pas une anomalie, et le comblement des
# trous se fait en silver, pas ici. Bronze recopie ce que la source a dit.
DDL = """
create schema if not exists externe;

create table if not exists externe.taux_change (
    jour        date        not null,
    devise      text        not null,
    taux        numeric(12, 6) not null,
    charge_le   timestamptz not null default now(),
    primary key (jour, devise)
);

create table if not exists externe.jours_feries (
    jour        date        not null,
    pays        text        not null,
    nom         text        not null,
    nom_local   text        not null,
    national    boolean     not null,
    charge_le   timestamptz not null default now(),
    primary key (jour, pays, nom)
);
"""


def url_base() -> str:
    """Chaine de connexion, reprise a l'API plutot que redefinie.

    Deux configurations de connexion qui derivent l'une de l'autre est une
    panne qui attend son heure.
    """
    url = os.environ.get("DWH_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        env = pathlib.Path(__file__).resolve().parents[2] / "hanabi-back" / ".env"
        if env.exists():
            for ligne in env.read_text(encoding="utf-8").splitlines():
                if ligne.startswith("DATABASE_URL="):
                    url = ligne.split("=", 1)[1].strip()
                    break
    if not url:
        sys.exit("Aucune chaine de connexion. Renseigner DWH_DATABASE_URL.")
    if not url.startswith("postgres"):
        sys.exit("Ces sources ne se chargent que dans PostgreSQL.")
    return url


# Frankfurter renvoie 403 sur l'agent par defaut d'urllib, qui ressemble a
# celui d'un aspirateur de site. Se nommer est de toute facon la politesse
# minimale envers un service gratuit : l'exploitant sait qui l'appelle et peut
# joindre quelqu'un avant de bloquer.
AGENT = "hanabi-dwh/1.0 (+https://github.com/SouleimanME/hanabi)"


def lire_json(url: str, essais: int = 3):
    """Appel HTTP avec reprise.

    Une source externe tombe, c'est sa nature. Trois tentatives espacees
    valent mieux qu'un plantage qui oblige a relancer toute la chaine, et
    l'attente croissante evite d'insister sur un service deja en difficulte.
    """
    dernier = None
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
    for essai in range(essais):
        try:
            with urllib.request.urlopen(requete, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            dernier = e
            if essai < essais - 1:
                import time

                time.sleep(2**essai)
    raise RuntimeError(f"{url} injoignable apres {essais} essais : {dernier}")


def decoupe(debut: dt.date, fin: dt.date, jours: int = 365):
    """Decoupe une plage en tranches.

    Frankfurter accepte de longues plages, mais une requete par annee garde
    les reponses de taille previsible et rend le rattrapage reprenable : si la
    troisieme tranche echoue, les deux premieres sont deja en base.
    """
    curseur = debut
    while curseur <= fin:
        bout = min(curseur + dt.timedelta(days=jours - 1), fin)
        yield curseur, bout
        curseur = bout + dt.timedelta(days=1)


def charge_taux(cx, debut: dt.date, fin: dt.date) -> int:
    lignes = []
    for a, b in decoupe(debut, fin):
        data = lire_json(f"{API_TAUX}/{a}..{b}?base=EUR&symbols={DEVISE}")
        for jour, taux in sorted(data.get("rates", {}).items()):
            if DEVISE in taux:
                lignes.append((dt.date.fromisoformat(jour), DEVISE, taux[DEVISE]))

    with cx.cursor() as c:
        c.executemany(
            """insert into externe.taux_change (jour, devise, taux)
               values (%s, %s, %s)
               on conflict (jour, devise)
               do update set taux = excluded.taux, charge_le = now()""",
            lignes,
        )
        # `rowcount` apres un upsert compte les lignes reellement ecrites, la
        # ou `len(lignes)` compterait celles recues. Les deux different des
        # qu'une date revient a la jointure de deux tranches, et annoncer un
        # chiffre qui n'est pas celui de la table est le debut des ennuis.
        return c.rowcount


def charge_feries(cx, de: int, a: int) -> int:
    lignes = []
    for annee in range(de, a + 1):
        for pays in PAYS:
            for f in lire_json(f"{API_FERIES}/{annee}/{pays}"):
                # `global` a faux signalerait un ferie regional. Sur 2024-2027
                # la source ne renvoie que des feries nationaux pour la France
                # et le Japon, mais la colonne est conservee : le jour ou elle
                # remontera le Vendredi saint d'Alsace-Moselle, le compter
                # comme national fausserait le calendrier de tout le pays.
                # Une colonne gardee coute une colonne ; une hypothese gardee
                # coute une correction en production.
                lignes.append(
                    (
                        dt.date.fromisoformat(f["date"]),
                        pays,
                        f["name"],
                        f.get("localName") or f["name"],
                        bool(f.get("global", True)),
                    )
                )

    with cx.cursor() as c:
        c.executemany(
            """insert into externe.jours_feries (jour, pays, nom, nom_local, national)
               values (%s, %s, %s, %s, %s)
               on conflict (jour, pays, nom)
               do update set nom_local = excluded.nom_local,
                             national  = excluded.national,
                             charge_le = now()""",
            lignes,
        )
        return c.rowcount


def accorde_lecture(cx) -> None:
    """Meme geste que le hook de fin d'execution dbt.

    Sans ces droits, les tables sont invisibles depuis la console Neon et
    depuis la console SQL du back-office, ce qui donne l'impression que le
    chargement a echoue.
    """
    with cx.cursor() as c:
        c.execute("grant usage on schema externe to public")
        c.execute("grant select on all tables in schema externe to public")
        c.execute(
            "alter default privileges in schema externe grant select on tables to public"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Extraction des sources externes.")
    sous = p.add_subparsers(dest="quoi", required=True)

    t = sous.add_parser("taux", help="taux EUR vers JPY")
    t.add_argument("--depuis", default="2024-08-01")
    t.add_argument("--jusqua", default=str(dt.date.today()))

    f = sous.add_parser("feries", help="jours feries FR et JP")
    f.add_argument("--de", type=int, default=2024)
    f.add_argument("--a", type=int, default=dt.date.today().year + 1)

    sous.add_parser("tout", help="les deux, sur la fenetre par defaut")

    args = p.parse_args()
    with psycopg.connect(url_base(), autocommit=True) as cx:
        with cx.cursor() as c:
            c.execute(DDL)

        if args.quoi in ("taux", "tout"):
            debut = dt.date.fromisoformat(getattr(args, "depuis", "2024-08-01"))
            fin = dt.date.fromisoformat(getattr(args, "jusqua", str(dt.date.today())))
            print(f"[taux]   {charge_taux(cx, debut, fin)} cotations, {debut} a {fin}")

        if args.quoi in ("feries", "tout"):
            de = getattr(args, "de", 2024)
            a = getattr(args, "a", dt.date.today().year + 1)
            print(f"[feries] {charge_feries(cx, de, a)} jours, {de} a {a}, {'/'.join(PAYS)}")

        accorde_lecture(cx)


if __name__ == "__main__":
    main()
