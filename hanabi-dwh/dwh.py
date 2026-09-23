#!/usr/bin/env python
"""Lance dbt avec la connexion de l'application.

- reprend `DATABASE_URL` de `hanabi-back/.env` si l'environnement ne la fournit pas ;
- la découpe en variables `DWH_*` pour `profiles.yml` (mot de passe décodé) ;
- pointe `--profiles-dir` sur ce dossier ;
- refuse une base qui n'est pas PostgreSQL.

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
    """Reprend `DATABASE_URL` du .env de l'API, sauf si l'environnement la fournit."""
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
    """Traduit l'URL en variables `DWH_*` et rend l'hôte visé.

    `obligatoire=False` rend None au lieu de quitter : Dagster doit pouvoir
    charger le graphe sans base.
    """
    url = os.environ.get("DWH_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        if not obligatoire:
            return None
        sys.exit(
            "Aucune base indiquée. Renseigne DATABASE_URL dans hanabi-back/.env,\n"
            "ou exporte DWH_DATABASE_URL pour viser une autre base."
        )
    if not url.startswith(("postgres://", "postgresql://")):
        if not obligatoire:
            return None
        moteur = url.split("://")[0] or "inconnu"
        sys.exit(
            f"L'entrepôt ne se construit que sur PostgreSQL (base visée : {moteur}).\n"
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
        # TLS exigé par Neon, absent d'un conteneur local
        "DWH_SSLMODE": "prefer" if hote in ("localhost", "127.0.0.1") else "require",
    }
    for cle, valeur in variables.items():
        # Une variable posée explicitement l'emporte
        os.environ.setdefault(cle, valeur)
    return os.environ["DWH_HOST"]


def executable_dbt() -> str:
    """Exécutable `dbt` du venv, déduit de `sys.executable` (le venv n'est pas toujours activé)."""
    dbt = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    return str(dbt) if dbt.exists() else "dbt"


def main() -> int:
    charge_env_api()
    hote = pose_variables_dbt()

    # Hôte affiché, jamais les identifiants
    print(f"[dwh] base visée : {hote}", file=sys.stderr)

    return subprocess.call([
        executable_dbt(),
        *(sys.argv[1:] or ["build"]),
        "--profiles-dir", str(RACINE),
        "--project-dir", str(RACINE),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
