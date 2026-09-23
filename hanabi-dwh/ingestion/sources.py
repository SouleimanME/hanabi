# -*- coding: utf-8 -*-
"""Extraction des sources externes de l'entrepôt.

- Taux EUR/JPY (Frankfurter, BCE) : le coût fournisseur est en yen, la marge en
  euros ; la série sépare l'effet du prix de celui du change.
- Jours fériés français (demande des clients) et japonais (réassort des
  fournisseurs), gardés distincts.

Les données vont dans le schéma `externe`, propriété de la chaîne de données et
non de l'application (pas de migration Alembic). Chargements en
`INSERT ... ON CONFLICT DO UPDATE` : rejouer une fenêtre est sans effet.
Utilisable seul ou via `orchestration/actifs_externes.py`.

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

# Taux de référence de la BCE, sans clé, historique depuis 1999
API_TAUX = "https://api.frankfurter.dev/v1"

# Même schéma de réponse pour tous les pays
API_FERIES = "https://date.nager.at/api/v3/PublicHolidays"

DEVISE = "JPY"
PAYS = ("FR", "JP")

# Fenêtres par défaut, partagées avec les partitions Dagster
DEBUT_TAUX = "2024-08-01"
PREMIERE_ANNEE_FERIES = 2024

# La BCE ne cote ni le week-end ni ses fériés ; les trous se comblent en silver
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
    """Chaîne de connexion, reprise de l'API."""
    url = os.environ.get("DWH_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        env = pathlib.Path(__file__).resolve().parents[2] / "hanabi-back" / ".env"
        if env.exists():
            for ligne in env.read_text(encoding="utf-8").splitlines():
                if ligne.startswith("DATABASE_URL="):
                    url = ligne.split("=", 1)[1].strip()
                    break
    if not url:
        sys.exit("Aucune chaîne de connexion. Renseigner DWH_DATABASE_URL.")
    if not url.startswith("postgres"):
        sys.exit("Ces sources ne se chargent que dans PostgreSQL.")
    return url


# Frankfurter refuse l'agent par défaut d'urllib ; on se nomme
AGENT = "hanabi-dwh/1.0 (+https://github.com/SouleimanME/hanabi)"


def ouvre_base():
    """Connexion en autocommit ; le DDL `if not exists` rend un premier chargement autonome."""
    cx = psycopg.connect(url_base(), autocommit=True)
    with cx.cursor() as c:
        c.execute(DDL)
    return cx


def lire_json(url: str, essais: int = 3):
    """Appel HTTP avec trois tentatives espacées."""
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
    raise RuntimeError(f"{url} injoignable après {essais} essais : {dernier}")


def decoupe(debut: dt.date, fin: dt.date, jours: int = 365):
    """Découpe une plage en tranches annuelles, reprenables une à une."""
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
        # Lignes écrites, pas lignes reçues
        return c.rowcount


def charge_feries(cx, de: int, a: int) -> int:
    lignes = []
    for annee in range(de, a + 1):
        for pays in PAYS:
            for f in lire_json(f"{API_FERIES}/{annee}/{pays}"):
                # `global` à faux : férié régional, conservé pour ne pas le compter comme national
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
    """Droits de lecture, comme le crochet de fin d'exécution dbt."""
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
    t.add_argument("--depuis", default=DEBUT_TAUX)
    t.add_argument("--jusqua", default=str(dt.date.today()))

    f = sous.add_parser("feries", help="jours fériés FR et JP")
    f.add_argument("--de", type=int, default=PREMIERE_ANNEE_FERIES)
    f.add_argument("--a", type=int, default=dt.date.today().year + 1)

    sous.add_parser("tout", help="les deux, sur la fenêtre par défaut")

    args = p.parse_args()
    with ouvre_base() as cx:
        if args.quoi in ("taux", "tout"):
            debut = dt.date.fromisoformat(getattr(args, "depuis", DEBUT_TAUX))
            fin = dt.date.fromisoformat(getattr(args, "jusqua", str(dt.date.today())))
            print(f"[taux]   {charge_taux(cx, debut, fin)} cotations, {debut} a {fin}")

        if args.quoi in ("feries", "tout"):
            de = getattr(args, "de", PREMIERE_ANNEE_FERIES)
            a = getattr(args, "a", dt.date.today().year + 1)
            print(f"[feries] {charge_feries(cx, de, a)} jours, {de} a {a}, {'/'.join(PAYS)}")

        accorde_lecture(cx)


if __name__ == "__main__":
    main()
