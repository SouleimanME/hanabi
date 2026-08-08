#!/usr/bin/env python
"""Lance dbt avec la connexion de l'application.

Quatre corvees en une commande :

- charger `hanabi-back/.env` si `DATABASE_URL` n'est pas deja dans
  l'environnement, pour que la chaine de connexion ne vive qu'a un seul
  endroit ;
- la decouper en variables `DWH_*`, que lit `profiles.yml`. dbt-postgres attend
  cinq champs separes la ou l'application manipule une URL ; le decoupage se
  fait ici, avec `urllib`, plutot que de demander la saisie des memes
  identifiants une seconde fois sous cinq noms differents - et `urllib` decode
  au passage les caracteres echappes en pourcent d'un mot de passe, ce qu'un
  decoupage a la main oublie invariablement ;
- pointer `--profiles-dir` sur ce dossier plutot que sur le `~/.dbt` que dbt
  cherche par defaut : le profil est versionne avec le projet, puisqu'il ne
  contient aucune valeur en dur ;
- refuser de partir si la base visee n'est pas PostgreSQL. Le SQL de l'entrepot
  emploie `date_trunc`, `generate_series` et des fonctions de fenetrage : sur
  une base SQLite, dbt echouerait plus loin avec une erreur bien moins parlante.

    python dwh.py build             construit tout et joue les tests
    python dwh.py run               construit sans tester
    python dwh.py test              joue les tests seuls
    python dwh.py run -s gold       ne reconstruit que la couche gold
    python dwh.py docs generate     produit la documentation et le graphe
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

RACINE = Path(__file__).resolve().parent
ENV_API = RACINE.parent / "hanabi-back" / ".env"


def charge_env_api() -> None:
    """Reprend `DATABASE_URL` du fichier .env de l'API, s'il n'est pas deja pose.

    Lecture volontairement naive : ce fichier est une suite de `CLE=valeur`, pas
    un script shell. Ajouter python-dotenv pour dix lignes reviendrait a
    installer une dependance de plus dans un projet qui en compte peu.

    La variable deja presente dans l'environnement gagne : c'est elle qui permet
    de viser une base jetable sans toucher au fichier de l'API.
    """
    if os.environ.get("DATABASE_URL") or os.environ.get("DWH_DATABASE_URL"):
        return
    if not ENV_API.exists():
        return
    for ligne in ENV_API.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        if cle.strip() in ("DATABASE_URL", "DWH_DATABASE_URL"):
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def pose_variables_dbt(obligatoire: bool = True) -> str | None:
    """Traduit l'URL de connexion en variables `DWH_*`, et rend l'hote vise.

    `obligatoire=False` rend None au lieu de s'arreter, et sert a l'unique
    appelant qui n'a pas le droit de mourir : le paquet `orchestration/`, dont
    Dagster charge les definitions au demarrage du serveur de code. Un
    `sys.exit` a l'import rendrait l'interface inaccessible sur une machine sans
    base, la ou l'on veut au contraire pouvoir lire le graphe hors ligne - c'est
    aussi ce que fait la CI, qui joue `dbt parse` sans identifiants.
    """
    url = os.environ.get("DWH_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        if not obligatoire:
            return None
        sys.exit(
            "Aucune base indiquee. Renseigne DATABASE_URL dans hanabi-back/.env,\n"
            "ou exporte DWH_DATABASE_URL pour viser une autre base."
        )
    if not url.startswith(("postgres://", "postgresql://")):
        if not obligatoire:
            return None
        moteur = url.split("://")[0] or "inconnu"
        sys.exit(
            f"L'entrepot ne se construit que sur PostgreSQL (base visee : {moteur}).\n"
            "En local, un PostgreSQL jetable suffit :\n"
            "  docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=hanabi "
            "-e POSTGRES_DB=hanabi --name hanabi-pg postgres:16"
        )

    parts = urlparse(url)
    hote = parts.hostname or "localhost"
    variables = {
        "DWH_HOST": hote,
        "DWH_PORT": str(parts.port or 5432),
        "DWH_USER": unquote(parts.username or ""),
        "DWH_PASSWORD": unquote(parts.password or ""),
        "DWH_DBNAME": (parts.path or "/").lstrip("/") or "postgres",
        # Neon exige TLS, un conteneur local ne le propose pas. Le reglage se
        # deduit de l'hote plutot que d'etre impose : sans cela, l'un des deux
        # cas echoue systematiquement.
        "DWH_SSLMODE": "prefer" if hote in ("localhost", "127.0.0.1") else "require",
    }
    for cle, valeur in variables.items():
        # `setdefault` : une variable posee explicitement par l'utilisateur
        # l'emporte sur ce qui est deduit de l'URL.
        os.environ.setdefault(cle, valeur)
    return os.environ["DWH_HOST"]


def executable_dbt() -> str:
    """Chemin de l'executable `dbt` installe a cote de l'interpreteur.

    Deduit de `sys.executable` plutot que cherche dans le PATH : le venv n'est
    pas toujours active. Dagster lance ses serveurs de code par un chemin
    absolu, sans passer par un shell ou `.venv/Scripts` figurerait, et un
    `dbt introuvable` a cet endroit est aussi opaque qu'evitable.

    Un executable plutot que `python -m dbt.cli.main` : ce dernier reimporte un
    paquet deja charge et fait bruire un avertissement a chaque appel.
    """
    dbt = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    return str(dbt) if dbt.exists() else "dbt"


def main() -> int:
    charge_env_api()
    hote = pose_variables_dbt()

    # L'hote est affiche, jamais les identifiants : construire l'entrepot dans
    # la base de production en croyant viser un conteneur local est exactement
    # l'erreur que ce rappel evite.
    print(f"[dwh] base visee : {hote}", file=sys.stderr)

    return subprocess.call([
        executable_dbt(),
        *(sys.argv[1:] or ["build"]),
        "--profiles-dir", str(RACINE),
        "--project-dir", str(RACINE),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
