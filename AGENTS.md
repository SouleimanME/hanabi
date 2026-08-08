# AGENTS.md

Contexte destiné aux agents IA qui interviennent sur ce dépôt. Il décrit ce que le
code fait, comment le lancer, et les conventions à respecter pour qu'une
contribution automatisée reste cohérente avec l'existant.

Les humains ont le [README.md](README.md) pour la présentation et
[DEPLOY.md](DEPLOY.md) pour la mise en ligne. Ce fichier-ci ne les remplace pas, il
répond aux questions qu'un agent se pose avant de modifier quoi que ce soit.

---

## 1. Le projet en trois phrases

Hanabi est une boutique en ligne fictive d'objets japonais, écrite comme projet de
portfolio. Le dépôt contient deux applications indépendantes : une API REST FastAPI
et une interface React servie séparément. Aucun paiement réel n'est capturé et aucun
e-mail n'est envoyé - les deux sont simulés, et c'est volontaire.

## 2. Structure

```
hanabi-back/          API FastAPI + SQLAlchemy
  app/
    main.py           Assemblage de l'app, middlewares, lifespan (migrations + seed)
    config.py         Réglages (pydantic-settings), lus depuis .env ou l'environnement
    database.py       Engine (SQLite ou PostgreSQL), SessionLocal, Base, get_db
    migrate.py        Application des migrations Alembic au démarrage
    models.py         Tables SQLAlchemy - source de vérité du schéma
    schemas.py        Modèles Pydantic d'entrée/sortie
    deps.py           get_current_user / get_admin_user / get_admin_writer
    security.py       Hachage bcrypt, création et lecture des jetons JWT
    passwords.py      Politique de mot de passe côté serveur (NIST SP 800-63B)
    antibot.py        Preuve de travail, pot de miel, throttling par e-mail et par IP
    ratelimit.py      slowapi, en-têtes de sécurité, limite de taille du corps
    pricing.py        Recalcul du panier côté serveur (remises, port, total)
    analytics.py      Tous les calculs décisionnels du back-office
    warehouse.py      Lecture des tables d'agrégats construites par dbt
    seed.py           Catalogue de démonstration + provisionnement administrateur
    demo_data.py      Jeu de données analytique (comptes, commandes, vues)
    translations.py   Traductions du catalogue (fr/en/es)
    routers/          Un fichier par domaine : auth, products, orders, reviews,
                      promos, newsletter, admin, security, warehouse
  migrations/         Révisions Alembic ; `env.py` lit l'URL dans la config
  alembic.ini         Configuration Alembic (sans URL, volontairement)
  tests/              pytest, base SQLite en mémoire par test
hanabi-front/         Interface React (Vite), sans framework de routage
  src/
    App.jsx           Racine : état global, routage maison via lib/routes.js
    lib/api.js        Client HTTP unique - tout appel réseau passe par ici
    pages/            Home, ProductPage, Checkout, Account, Confirmation, Saved…
    components/       Découpés par domaine (layout, catalog, cart, modals, ui, brand)
    hooks/            Un hook par préoccupation (panier, auth, thème, antibot…)
    i18n/             Dictionnaires fr / en / es
    admin/            Back-office, application dans l'application
    styles/           CSS par domaine, jetons de design dans tokens.css
hanabi-dwh/           Entrepôt décisionnel (dbt), voir son propre README
  models/bronze/      Vues sur les tables de l'application et sur les sources externes
  models/silver/      Données nettoyées et conformées ; les règles métier vivent ici
  models/gold/        Une table d'agrégats par question métier
  macros/             Nommage des schémas, deux tests génériques maison
  ingestion/          Extraction des sources publiques (taux BCE, jours fériés)
  orchestration/      Graphe d'actifs Dagster : ingestion + modèles dbt
    ressources.py     Projet dbt et connexion, reprises de dwh.py
    actifs_dbt.py     Traducteur de clés et de groupes, puis les 27 modèles
    actifs_externes.py  Les deux extractions, dont une partitionnée par mois
    planification.py  Le travail et son calendrier quotidien
  dwh.py              Lanceur : reprend DATABASE_URL et appelle dbt
docs/                 Captures utilisées par le README
render.yaml           Blueprint de déploiement de l'API
hanabi-front/public/_redirects   Repli SPA (Cloudflare Pages)
```

## 3. Lancer le projet

Deux terminaux. L'API d'abord, le front ensuite.

```bash
cd hanabi-back && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
```

```bash
cd hanabi-back && .venv/Scripts/python -m uvicorn app.main:app --reload
```

```bash
cd hanabi-front && npm install && npm run dev
```

L'API écoute sur `http://localhost:8000` (documentation interactive sur `/docs`), le
front sur `http://localhost:5173`. Le front lit l'URL de l'API dans
`hanabi-front/.env` (`VITE_API_URL`).

La base SQLite `hanabi-back/atelier.db` est créée et peuplée au premier démarrage.
Pour repartir de zéro : arrêter le serveur, supprimer le fichier, relancer.

### Vérifications avant de rendre la main

```bash
cd hanabi-back && .venv/Scripts/python -m pytest
```

```bash
cd hanabi-front && npm run lint && npm run format:check && npm run build
```

```bash
cd hanabi-dwh && .venv/Scripts/dbt parse --profiles-dir . --project-dir . && .venv/Scripts/dagster definitions validate
```

Un changement backend doit passer `pytest`. Un changement frontend doit passer les
trois commandes ci-dessus - `format:check` échoue si Prettier n'est pas passé, ce qui
est la cause la plus fréquente d'un échec d'intégration continue sur ce dépôt.
Un changement dans l'entrepôt doit passer les deux vérifications de la troisième
commande, qui sont celles de l'intégration continue : elles ne demandent aucune
base, `parse` compilant le Jinja et `validate` chargeant le graphe Dagster.

La suite tourne sur SQLite en mémoire, ce qui la rend rapide mais aveugle aux
écarts entre moteurs. Pour rejouer la même suite sur PostgreSQL :

```bash
docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=hanabi -e POSTGRES_DB=hanabi --name hanabi-pg postgres:16
```

puis exporter `DATABASE_URL=postgresql://postgres:hanabi@localhost:5433/hanabi`
avant de lancer l'application. À faire après toute modification de requête
analytique.

## 4. Conventions

### Langue

**Le code, les commentaires et les messages de commit sont en français.** Les
identifiants techniques restent en anglais quand l'écosystème l'impose
(`created_at`, `price_cents`, `get_db`). Les messages d'erreur rendus à
l'utilisateur sont en français et doivent dire quoi corriger, pas seulement ce qui a
échoué.

Les commentaires expliquent **pourquoi**, jamais **quoi**. Le dépôt en contient
beaucoup et ils sont substantiels : ils documentent une décision, un piège
rencontré, ou une limite assumée. Un agent qui ajoute `# incrémente le compteur`
au-dessus de `i += 1` produit du bruit ; un agent qui touche à une ligne commentée
doit lire le commentaire avant, et le mettre à jour si sa raison d'être change.

Le back-office (`hanabi-front/src/admin/`) est monolingue français et n'est pas
traduit : il s'adresse à l'équipe de la boutique, pas aux clients.

### Argent

**Les montants sont des entiers en centimes, jamais des flottants.** Le suffixe
`_cents` est obligatoire sur ces champs. Le formatage en euros se fait à l'affichage
(`lib/format.js` côté front, à la sérialisation côté API). Toute arithmétique en
`float` sur un prix est un bug.

### Sécurité

Le projet applique quelques règles non négociables, chacune commentée à l'endroit
où elle vit :

- **Aucun secret dans le dépôt.** `SECRET_KEY`, `ADMIN_EMAIL` et `ADMIN_PASSWORD`
  viennent de l'environnement. En `ENV=prod`, l'absence de `SECRET_KEY` empêche le
  démarrage plutôt que de laisser signer des jetons avec une clé connue.
- **Le panier est recalculé côté serveur** dans `pricing.py`. Un prix envoyé par le
  client n'est jamais cru.
- **Les routes `/admin` vérifient `is_admin` côté serveur** via `get_admin_user`. Le
  masquage d'un bouton dans l'interface n'est pas un contrôle d'accès.
- **Le stock se décrémente par `UPDATE … WHERE stock >= qty`** et non par lecture
  puis écriture - deux acheteurs simultanés sur le dernier article ne doivent pas
  passer tous les deux.
- **La politique de mot de passe est celle de `passwords.py`**, appliquée côté
  serveur. La jauge du navigateur est une aide à la saisie, pas un contrôle.

### Front

- Tout appel réseau passe par `src/lib/api.js`. Pas de `fetch` dispersé dans les
  composants - le back-office fait exception et réutilise `API_BASE` exporté par ce
  module.
- Pas de bibliothèque de graphiques : les visualisations du back-office sont du SVG
  écrit à la main (`BarChart`, `DonutChart`, `LineChart`… dans `admin/Admin.jsx`).
  Ne pas introduire de dépendance pour en ajouter une.
- Les couleurs viennent des jetons CSS de `styles/tokens.css`. Le thème clair et le
  thème sombre doivent tous deux rester lisibles.
- Toute chaîne visible par un client passe par les dictionnaires `i18n/` et doit
  être ajoutée aux **trois** langues (fr, en, es).

### Base de données

**Deux moteurs.** SQLite en développement et pour la suite de tests, PostgreSQL
(Neon) en production. `models.py` reste la source de vérité du schéma.

**Le schéma évolue par migrations Alembic**, appliquées au démarrage par
`app/migrate.py`. Après avoir modifié `models.py` :

```bash
cd hanabi-back && .venv/Scripts/alembic revision --autogenerate -m "ce que fait la migration"
```

Relire systématiquement le fichier généré : l'autogénération détecte mal les
renommages, qu'elle traduit en une suppression suivie d'une création - soit une
perte de données sur une base en production. Une migration qui supprime une
colonne doit être signalée explicitement dans la réponse.

**Conséquence directe pour un agent : les requêtes doivent rester portables.**
Pas de `strftime` (SQLite seul), pas de `date_trunc` ni de `to_char`
(PostgreSQL seul). `analytics.py` regroupe par mois via les sept premiers
caractères de la date écrite en texte, forme ISO commune aux deux moteurs. Une
requête testée uniquement sur SQLite peut parfaitement échouer en production ;
en cas de doute, lancer un PostgreSQL jetable en conteneur et y rejouer la suite
(voir plus bas).

**Cette règle ne s'applique pas à `hanabi-dwh/`**, qui ne vise que PostgreSQL et
emploie donc librement `date_trunc`, `generate_series` et les fonctions de
fenêtrage. La frontière est nette : tout ce qui vit dans `hanabi-back/app/` doit
rester portable, tout ce qui vit dans `hanabi-dwh/models/` n'a pas à l'être.

Sur PostgreSQL, **les clés étrangères ne sont pas indexées automatiquement**,
contrairement à ce que beaucoup supposent. Toute nouvelle colonne servant à une
jointure ou à un filtre analytique doit porter `index=True`.

### Entrepôt décisionnel

`hanabi-dwh/` construit trois schémas - `bronze`, `silver`, `gold` - dans la
même base Neon, en architecture médaillon. Le back-office les lit par l'onglet
« Entrepôt », via `app/warehouse.py`, qui ne fait qu'un `SELECT … LIMIT` : aucun
calcul n'y a sa place, c'est le travail de dbt. Le README du dossier détaille les
modèles ; trois points concernent directement un agent :

- **Deux chemins coexistent, et c'est voulu.** `analytics.py` lit la base
  transactionnelle et rend les chiffres de l'instant ; l'entrepôt rend ceux de la
  dernière construction. Ajouter un indicateur d'un côté ne le fait pas
  apparaître de l'autre - décider lequel des deux est concerné fait partie de la
  tâche.
- **Une règle métier dupliquée est un bug en attente.** `REVENUE_STATUSES` côté
  API et la variable `statuts_ca` de `dbt_project.yml` doivent rester
  identiques ; il en va de même pour le découpage des tranches d'âge et pour la
  fenêtre de 90 jours de la vitesse d'écoulement. Toucher à l'un impose de
  vérifier l'autre.
- **La notation RFM existe en double et doit rester à l'identique.**
  `_score_par_rang` dans `analytics.py` et le bloc `positions`/`scores` de
  `gold_clients_rfm.sql` calculent la même chose : un quintile de population,
  attribué au rang médian de chaque groupe d'ex aequo. Les deux arrondissent
  vers le bas (`int` d'un côté, `floor` de l'autre), condition sans laquelle ils
  divergeraient sur les valeurs tombant exactement sur une borne. La récence se
  compte en jours de calendrier des deux côtés - `(maintenant.date() -
  derniere.date()).days` et `current_date - date` - et non en tranches de 24 h.
  Toute modification de l'un se vérifie en comparant les effectifs des sept
  segments entre `/admin/analytics/segments` et
  `/admin/warehouse/marts/segments_rfm` : ils doivent être égaux.
- **La console SQL est en lecture seule, et ça ne se relâche pas.**
  `warehouse.executer_sql` ouvre une saisie SQL libre au back-office, refermée
  par cinq barrières indépendantes : transaction `READ ONLY`, `statement_timeout`,
  examen du plan via `EXPLAIN` pour connaître les tables réellement lues,
  contrôle de forme, authentification. Ajouter `public` à `SCHEMAS_AUTORISES`
  exposerait `users.password_hash` ; un test le verrouille. Le contrôle de forme
  ignore délibérément les mots-clefs situés dans une chaîne ou un commentaire -
  filtrer sur la valeur `'Delete me'` est légitime.
- **L'entrepôt n'existe pas sur SQLite.** `warehouse.py` le détecte et rend un
  état « non construit » plutôt qu'une erreur ; la suite de tests vérifie ce
  comportement, elle ne vérifie pas le contenu des agrégats - ce sont les tests
  dbt qui s'en chargent, sur PostgreSQL.

### Orchestration

`hanabi-dwh/orchestration/` déclare la chaîne comme un graphe d'actifs Dagster :
les deux extractions de `ingestion/` en amont, les 27 modèles dbt en aval. Cinq
points concernent un agent :

- **L'ordre ne s'écrit plus nulle part.** `brz_taux_change` dépend de
  `externe/taux_change` parce que la source dbt et l'actif Python portent la
  **même clé**, produite par `TraducteurHanabi.get_asset_key` à partir du schéma
  PostgreSQL. Renommer un schéma de source dans `models/sources.yml` sans
  renommer la clé de l'actif correspondant coupe le graphe en deux moitiés qui
  s'exécutent quand même, sans erreur - le lignage est alors faux et rien ne le
  dit. C'est la seule couture fragile de l'ensemble.
- **Dagster ne réimplémente pas dbt**, il lance `dbt build` et lit son flux
  d'événements. Un changement de modèle ne demande aucune modification côté
  Dagster ; le graphe se régénère depuis `target/manifest.json`.
- **`from __future__ import annotations` est absent de `actifs_dbt.py` et
  `actifs_externes.py`, et doit le rester.** Dagster compare l'annotation du
  paramètre `context` au type réel pour décider quoi passer à la fonction ; des
  annotations différées ne sont plus que des chaînes, et l'erreur obtenue
  affirme qu'`AssetExecutionContext` n'est pas `AssetExecutionContext`.
- **`dbt-core` est plafonné à 1.11 par `dagster-dbt`**, qui vérifie la version
  du manifeste qu'il lit. Remonter dbt casse le chargement des définitions ; les
  deux se remontent ensemble.
- **Le calendrier Dagster ne s'exécute que sous `dagster dev`.** Aucun daemon
  n'est déployé : en ligne, c'est toujours `.github/workflows/entrepot.yml` qui
  déclenche, à la même heure. Modifier l'une des deux plages horaires impose de
  vérifier l'autre.

Après avoir modifié un modèle :

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py build
```

Pour lire le graphe, rattraper une partition ou relancer un seul nœud :

```bash
cd hanabi-dwh && .venv/Scripts/dagster dev
```

Une construction ne touche jamais au schéma `public` : elle le lit et n'écrit
que dans ses propres schémas.

**Les droits de lecture se reposent à chaque construction**, par le crochet
`on-run-end` de `dbt_project.yml`. Un schéma PostgreSQL nouvellement créé
n'accorde `USAGE` à personne d'autre que son propriétaire, et une table recréée
perd les droits de celle qu'elle remplace : un agent qui remplacerait ce crochet
par un `GRANT` joué une fois rendrait l'entrepôt invisible à la construction
suivante, sans erreur ni avertissement.

## 5. Pièges connus

- **Deux mises en veille se cumulent.** Render endort le service web après quinze
  minutes sans trafic, Neon endort la base après cinq. La première requête peut
  donc payer les deux réveils : une cinquantaine de secondes pour le conteneur,
  quelques centaines de millisecondes pour la base. Un appel qui semble échouer
  est le plus souvent un réveil en cours.
- **Le pool doit tester ses connexions.** Quand Neon s'endort, les connexions du
  pool sont coupées côté serveur sans que le client en soit averti. C'est
  `pool_pre_ping=True` dans `database.py` qui évite qu'une requête sur deux
  échoue au réveil ; ne pas le retirer.
- **Le disque du conteneur reste éphémère.** Seule la base est persistante
  désormais. Rien ne doit être écrit sur le système de fichiers en production
  avec l'espoir de le retrouver.
- **L'entrepôt ne se reconstruit que si le secret est posé.**
  `.github/workflows/entrepot.yml` le reconstruit chaque jour, mais la tâche
  s'arrête d'elle-même tant que `DWH_DATABASE_URL` n'est pas renseigné dans les
  secrets du dépôt - état normal sur un fork, et probablement l'état courant.
  `gold` reste alors figé sur la dernière exécution manuelle de `dwh.py build`,
  et l'interface affiche cet horodatage précisément pour qu'on ne s'y trompe
  pas. Un chiffre du tableau de bord qui diffère de celui de l'onglet analytique
  n'est presque jamais une erreur de calcul, c'est un entrepôt à reconstruire.
- **Le jeu de données de démonstration ne se génère qu'une fois.** Sur base
  persistante, `ensure_demo_dataset` voit que les comptes existent et ne fait
  rien. Pour le régénérer, il faut vider les tables - ce n'est plus un
  redéploiement qui s'en charge.
- **`.env` n'est pas déployé.** Les valeurs locales de `hanabi-back/.env` n'ont
  aucun effet en ligne ; les variables se saisissent dans le tableau de bord Render
  (`sync: false` dans `render.yaml` signifie exactement cela).
- **`hash_password` est lent, et c'est voulu.** bcrypt à 12 tours coûte environ
  0,3 s par appel. Ne jamais le boucler sur un gros volume : le générateur de
  données de démonstration calcule un condensat unique et le réutilise.
- **Le throttling se déclenche vite.** Huit échecs d'authentification en quinze
  minutes sur le même e-mail ou la même IP renvoient un 429. Un agent qui teste la
  connexion en boucle se bloque lui-même.
- **Les compteurs anti-robots sont en mémoire du processus.** Ils ne survivent pas à
  un redémarrage et ne sont pas partagés entre plusieurs instances. Documenté comme
  une limite assumée, pas comme un oubli.

## 6. Comptes de démonstration

| Compte | E-mail | Mot de passe | Rôle |
| --- | --- | --- | --- |
| Client | `demo@hanabi.fr` | `demo1234` | Client ordinaire, sans privilège |
| Back-office | `hanabi@atelier.fr` | `hanabi-logs2026` | Administrateur en lecture seule |

Ces deux comptes sont affichés dans la fenêtre de connexion : leurs identifiants
sont **publics par construction**. Le compte client n'a délibérément aucun droit
d'administration, et le compte back-office est bridé en lecture seule par
`DEMO_ADMIN_READONLY` (voir `deps.py`) pour qu'un visiteur ne puisse pas vider le
catalogue. Un agent ne doit pas leur accorder de droits d'écriture sans que la
demande soit explicite.

L'administrateur réel est provisionné séparément par `ADMIN_EMAIL` /
`ADMIN_PASSWORD`, qui n'apparaissent jamais dans le dépôt.

## 7. Attentes vis-à-vis d'une contribution automatisée

- Lire le code alentour avant d'écrire : la densité de commentaires, le nommage et
  le style d'un fichier doivent rester homogènes après passage.
- Ne pas reformater ce qui n'est pas touché, ne pas réorganiser des imports par
  goût, ne pas renommer sans raison.
- Ne pas ajouter de dépendance sans nécessité. Les listes de `requirements.txt` et
  `package.json` sont courtes, c'est délibéré.
- Signaler ce qui a été laissé de côté plutôt que de réduire silencieusement le
  périmètre demandé.
- Ne jamais écrire une valeur secrète en dur, même « temporairement », même dans un
  test.
