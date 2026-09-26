# Contribuer

Le [README](README.md) présente le projet, [DEPLOY.md](DEPLOY.md) sa mise en ligne.
Ce fichier rassemble ce qu'il faut savoir avant de modifier le code.

## Structure

```
hanabi-back/          API FastAPI + SQLAlchemy
  app/
    main.py           Assemblage, middlewares, démarrage (migrations + seed)
    config.py         Réglages lus dans l'environnement
    models.py         Tables, source de vérité du schéma
    pricing.py        Recalcul du panier côté serveur
    analytics.py      Calculs du back-office sur la base transactionnelle
    warehouse.py      Lecture des tables d'agrégats construites par dbt
    seed.py           Catalogue + provisionnement administrateur
    demo_data.py      Jeu de données de démonstration
    routers/          Un fichier par domaine
  migrations/         Révisions Alembic
  tests/              pytest, SQLite en mémoire ou PostgreSQL
hanabi-front/         Interface React (Vite)
  src/
    App.jsx           Racine de la boutique, routage via lib/routes.js
    lib/api.js        Client HTTP de la boutique
    pages/ components/ hooks/ i18n/
    styles/           CSS par domaine ; jetons dans tokens.css
    admin/            Back-office : Admin.jsx, views/, charts.jsx, admin.css
  e2e/                Parcours Playwright
hanabi-dwh/           Entrepôt dbt + orchestration Dagster (voir son README)
render.yaml           Déploiement de l'API
```

## Lancer

```bash
cd hanabi-back && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
```

```bash
cd hanabi-back && .venv/Scripts/python -m uvicorn app.main:app --reload
```

```bash
cd hanabi-front && npm install && npm run dev
```

API sur `http://localhost:8000` (`/docs`), front sur `http://localhost:5173`. La
base SQLite `hanabi-back/atelier.db` se crée au premier démarrage ; la supprimer
pour repartir de zéro.

Le démarrage joue les migrations, mais hors `ENV=prod` il ne migre qu'une base
locale : un `.env` qui viserait Neon mettrait la production en avance sur le code
déployé, qui ne redémarrerait plus. `MIGRER_BASE_DISTANTE=1` lève ce refus quand
la migration est voulue.

## Vérifier

```bash
cd hanabi-back && .venv/Scripts/python -m pytest
```

```bash
cd hanabi-front && npm run lint && npm run format:check && npm test && npm run build
```

```bash
cd hanabi-front && npx playwright test
```

```bash
cd hanabi-dwh && .venv/Scripts/dbt parse --profiles-dir . --project-dir . && .venv/Scripts/dagster definitions validate
```

`format:check` est l'échec de CI le plus fréquent : lancer `npm run format` avant
de pousser.

## Conventions

- **Français** pour le code métier, les commentaires et les commits
  (`type(scope) : Sujet`). Les identifiants imposés par l'écosystème restent en
  anglais (`created_at`, `price_cents`).
- **Commentaires courts**, pour dire pourquoi, pas quoi.
- **Argent en centimes entiers**, suffixe `_cents`. Formatage à l'affichage seulement.
- **Messages d'erreur** : dire quoi corriger.
- **Chaînes de la boutique** dans `i18n/`, en trois langues. Le back-office est en
  français seul.
- **Couleurs et mesures** tirées de `styles/tokens.css`, lisibles dans les deux thèmes.
- **Pas de nouvelle dépendance** sans nécessité : graphiques en SVG maison, pas de
  framework CSS ni de bibliothèque de composants.

## Sécurité

- Aucun secret dans le dépôt. En `ENV=prod`, l'API refuse de démarrer sans `SECRET_KEY`.
- Le panier est recalculé par `pricing.py` ; un prix venu du client n'est jamais cru.
- Les routes `/admin` vérifient `is_admin` côté serveur.
- Le stock se décrémente par `UPDATE … WHERE stock >= qty`.
- La console SQL de l'entrepôt reste en lecture seule ; `public` n'entre jamais dans
  `SCHEMAS_AUTORISES` (un test le verrouille).

## Base de données

SQLite en local et en test, PostgreSQL (Neon) en production ; la CI rejoue la suite
de l'API sur les deux. Dans `hanabi-back/app/`, les requêtes restent portables : ni
`strftime`, ni `date_trunc`. `hanabi-dwh/` ne vise que PostgreSQL et n'a pas cette
contrainte.

Après une modification de `models.py` :

```bash
cd hanabi-back && .venv/Scripts/alembic revision --autogenerate -m "ce que fait la migration"
```

Relire le fichier généré : un renommage devient une suppression suivie d'une création.
Indexer toute colonne de jointure ou de filtre (`index=True`) : PostgreSQL n'indexe pas
les clés étrangères.

Pour rejouer la suite sur PostgreSQL :

```bash
docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=hanabi -e POSTGRES_DB=hanabi --name hanabi-pg postgres:16
```

puis lancer `pytest` avec `TEST_DATABASE_URL=postgresql://postgres:hanabi@localhost:5433/hanabi`.
La variable n'accepte qu'une base locale : la suite en vide les tables entre deux
tests. Les migrations s'y jouent dans un schéma à part, `migrations`.

## Entrepôt

- `analytics.py` rend les chiffres de l'instant, l'entrepôt ceux de la dernière
  construction. Un indicateur ajouté d'un côté n'apparaît pas de l'autre.
- Règles dupliquées à garder identiques : `REVENUE_STATUSES` et `statuts_ca`
  (`dbt_project.yml`), les tranches d'âge, la fenêtre de 90 jours, la notation RFM
  (`_score_par_rang` et `gold_clients_rfm.sql`). Contrôle : les effectifs des segments
  de `/admin/analytics/segments` et `/admin/warehouse/marts/segments_rfm` sont égaux.
- Les ventes par catégorie lisent la catégorie figée sur la ligne de commande
  (`order_items.category`), des deux côtés ; références, audience et stock lisent la
  catégorie actuelle du produit.
- Un modèle ajouté dans `hanabi-dwh/models/` s'ajoute aussi à `COUCHES` dans
  `warehouse.py` (un test compare les deux).
- Les droits de lecture se reposent à chaque construction (`on-run-end`).
- `dbt-core` est plafonné par `dagster-dbt` : les deux se mettent à jour ensemble.
- `actifs_dbt.py` et `actifs_externes.py` n'importent pas
  `from __future__ import annotations` : Dagster lit l'annotation de `context`.
- Un modèle incrémental qui emploie une fonction de fenêtrage (`lag`, `avg over`)
  la calcule sur un contexte plus large que sa fenêtre de rattrapage, puis n'écrit
  que la fenêtre (voir `gold_ca_quotidien.sql`). La CI construit deux fois : le
  second passage, incrémental, doit redonner les mêmes chiffres.
- Une table incrémentale mal écrite par le passé se répare par une reconstruction
  complète : lancement manuel du workflow Entrepot, case cochée.

## Recherche

- Deux séries de requêtes dans `tests/recherche/` : `reglage.json` sert à régler
  seuils, usages et règles de prix ; `controle.json` ne sert qu'à mesurer. Régler
  en regardant la seconde la rend aussi optimiste que la première. Une requête
  ajoutée à `controle.json` après avoir vu un résultat n'a pas sa place.
- `python tests/recherche/banc.py` affiche chaque requête et son résultat, avec et
  sans modèle (`--sans-modele`). Les planchers de `test_recherche_banc.py` ne
  descendent jamais ; une amélioration les relève.
- Les tests coupent le sens par défaut (`RECHERCHE_SEMANTIQUE`) : un modèle chargé
  en arrière-plan au milieu d'un test changerait ses résultats. Sans modèle, les
  tests du sens sont sautés, sauf dans le job de CI qui pose `RECHERCHE_EXIGEE`.
- Changer de modèle, c'est changer `REVISION` et les empreintes de
  `plongement.py`, puis refaire le réglage : les scores d'un autre modèle n'ont pas
  la même échelle.
- Encoder un texte à la fois : le modèle quantifié calcule l'échelle de ses
  activations sur tout le lot, et un lot rendait les résultats dépendants des
  objets voisins.
- Pas de PyTorch : il ne tiendrait pas dans les 512 Mo de Render.

## Pièges

- Render endort l'API après quinze minutes, Neon la base après cinq : la première
  requête peut prendre une minute. La recherche par le sens revient quelques
  secondes plus tard, le temps d'encoder le catalogue ; d'ici là, la recherche par
  le texte répond.
- `pool_pre_ping=True` (`database.py`) évite les connexions mortes au réveil de Neon.
- Le disque du conteneur est éphémère.
- L'entrepôt ne se reconstruit chaque nuit que si `DWH_DATABASE_URL` est posé dans
  les secrets du dépôt.
- Le jeu de démonstration ne se génère qu'une fois ; vider les tables pour le refaire.
- bcrypt coûte environ 0,3 s par condensat : ne jamais le boucler.
- Huit échecs de connexion en quinze minutes renvoient un 429.
- Les compteurs anti-robots vivent en mémoire du processus.

## Comptes de démonstration

| Compte | E-mail | Mot de passe | Rôle |
| --- | --- | --- | --- |
| Client | `demo@hanabi.fr` | `demo1234` | Client sans privilège |
| Back-office | `hanabi@atelier.fr` | `hanabi-logs2026` | Administrateur en lecture seule |

Ces identifiants sont affichés dans la fenêtre de connexion. Le compte back-office
est bridé par `DEMO_ADMIN_READONLY`. L'administrateur réel vient de `ADMIN_EMAIL` et
`ADMIN_PASSWORD`, hors dépôt.
