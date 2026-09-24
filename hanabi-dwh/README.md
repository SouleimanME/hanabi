# hanabi-dwh : entrepôt décisionnel

Projet dbt qui construit, dans la base PostgreSQL de la boutique, trois schémas en
architecture **médaillon** : `bronze`, `silver`, `gold`. Le back-office lit `gold`
dans l'onglet **Entrepôt**, par un simple `SELECT … LIMIT`.

```
public (écrit par l'API)
   └─ bronze   vues, aucune transformation
        └─ silver   nettoyé, conformé, typé
             └─ gold   une table d'agrégats par question métier
                  └─ /admin/warehouse → onglet « Entrepôt »
```

---

## Deux chemins de lecture

`hanabi-back/app/analytics.py` répond aux mêmes questions sur la base
transactionnelle. Les deux coexistent :

| | `analytics.py` | l'entrepôt |
| --- | --- | --- |
| Source | base transactionnelle | instantané daté |
| Fraîcheur | l'instant | dernière construction |
| Coût de lecture | plusieurs agrégations | un `SELECT … LIMIT` |
| Règles métier | en Python, parfois répétées | une fois, en SQL, dans silver |

Un entrepôt construit par lots est en retard sur la base ; `gold.gold_execution`
date la construction et l'interface affiche cette date en permanence, avec une
alerte au-delà de 26 heures.

PostgreSQL est un moteur en lignes. À volume analytique réel, le médaillon irait
dans un moteur en colonnes (ClickHouse, DuckDB, BigQuery). À l'échelle de la
boutique, PostgreSQL suffit, et le projet vaut pour ses règles écrites une fois,
ses transformations testées et sa lignée lisible.

---

## Construire

```bash
cd hanabi-dwh && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py build
```

`dwh.py` :

- lit `DATABASE_URL` dans `hanabi-back/.env` si l'environnement ne la fournit pas ;
- la découpe en variables `DWH_*` pour `profiles.yml` (dbt-postgres attend des
  champs séparés) ;
- refuse une base qui n'est pas PostgreSQL ;
- **affiche l'hôte visé avant de commencer**, pour ne pas construire en production
  en croyant viser un conteneur local.

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py test
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run -s gold
```

`DWH_DATABASE_URL` l'emporte sur `DATABASE_URL` pour viser une autre base.

### Sur une base jetable

```bash
docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=hanabi -e POSTGRES_DB=hanabi --name hanabi-pg postgres:16
```

C'est la cible par défaut de `profiles.yml` quand dbt est lancé sans `dwh.py`.

La construction lit `public` et n'écrit que dans `bronze`, `silver` et `gold`.
Pour tout défaire : `drop schema bronze, silver, gold cascade;`.

### Droits de lecture

Un schéma neuf n'accorde `USAGE` qu'à son propriétaire : sans droits, la console
Neon et tout autre rôle reçoivent « permission denied for schema gold ».

`macros/droits.sql` accorde `usage` sur les trois schémas, `select` sur leurs
tables et les mêmes droits par défaut pour les tables à venir. Aucun droit
d'écriture.

La macro tourne en `on-run-end` : `dbt run` recrée les tables gold, et une table
recréée perd ses droits. Pour les reposer sans reconstruire :

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run-operation accorde_lecture
```

---

## Les trois couches

### bronze : 9 vues

Tables de l'application sous une forme stable, plus les deux sources externes du
schéma `externe`. Aucune donnée recopiée : `public` sert de zone d'atterrissage.

Restent dehors :

- **`password_hash`**, sans usage analytique ;
- **les coordonnées** : nom, e-mail, téléphone, adresse postale et adresse de
  livraison. Un client s'y désigne par son identifiant ; la console SQL du
  back-office, ouverte au compte de démonstration, n'a ainsi personne à montrer ;
- **les visuels** (`art`, `images`), dont les photos en base64.

Les colonnes sont énumérées : une colonne ajoutée à `users` n'entre dans
l'entrepôt que si on l'ajoute ici.

### silver : 7 modèles

Données nettoyées, typées, conformées, et règles métier écrites **une fois** :

- `slv_commandes.est_ca` : la règle du chiffre d'affaires, répétée en
  `status in (…)` dans une quinzaine de requêtes de l'API ;
- `slv_lignes_commande` : la marge, sur le prix et le coût **figés à l'achat**, et
  la catégorie figée elle aussi : un objet reclassé ne déplace pas ses ventes
  passées ;
- `slv_clients` : âge et tranche d'âge, déduits de l'année de naissance comme dans
  `analytics.py`, pour que les deux histogrammes concordent ;
- `slv_calendrier_mensuel` : un mois sans commande sort à zéro ;
- `slv_calendrier_quotidien` : même principe au jour, avec le taux de change
  reporté sur les jours non cotés et les fériés nationaux français et japonais en
  deux colonnes.

Tout est en vues sauf `slv_lignes_commande`, matérialisée en table : cinq modèles
gold la lisent.

### gold : 11 tables

| Table | Question |
| --- | --- |
| `gold_ca_quotidien` | Une journée faible est-elle un incident ou un jour férié, et la marge bouge-t-elle à cause des prix ou du yen ? |
| `gold_kpi_mensuel` | Comment le chiffre d'affaires, la marge et l'audience évoluent-ils mois par mois ? |
| `gold_performance_produit` | Quelles références rapportent, lesquelles font du volume sans marge ? |
| `gold_performance_categorie` | Quelle famille du catalogue porte réellement le résultat ? |
| `gold_segments_rfm` | Comment la clientèle se répartit-elle, et quelle part du chiffre pèse chaque segment ? |
| `gold_clients_rfm` | Qui sont les clients derrière chaque segment, et lesquels relancer ? |
| `gold_cohortes_retention` | Les clients recrutés un mois donné reviennent-ils les mois suivants ? |
| `gold_demographie_clients` | Ville, âge, civilité : quels profils achètent, et pour combien ? |
| `gold_promotions` | Quels codes font entrer du chiffre, et lesquels n'ont jamais servi ? |
| `gold_affinites_produits` | Quels articles s'achètent ensemble plus souvent que le hasard ? |
| `gold_execution` | De quand datent ces chiffres ? |

### La notation RFM

Les scores R, F et M sont des **quintiles de population** : « 5 » signifie « parmi
les 20 % de clients les mieux placés ».

La première version classait les *valeurs distinctes*. Avec 679 anciennetés sur
deux ans, « récence 5 » voulait dire « dans les 136 premières valeurs », et la
clientèle étant concentrée sur les achats récents :

| | avant | après |
| --- | ---: | ---: |
| clients notés R=5 | 73 % | 19,9 % |
| segment « À risque » | 19 clients (0,1 % du CA) | 5 430 clients (23,1 % du CA) |

Chaque valeur est désormais notée au **rang médian de son groupe d'ex aequo**, en
part de population (`cume_dist()` moins la demi-largeur du groupe). Les ex aequo
partagent leur score et le découpage porte sur la population.

Limite : un groupe d'ex aequo plus gros qu'un quintile ne se répartit pas. 64,9 %
des clients n'ont commandé qu'une fois et partagent le même score F.

Le calcul existe aussi dans `_score_par_rang` (`hanabi-back/app/analytics.py`). Les
deux doivent rester identiques ; ils donnent aujourd'hui les mêmes scores pour les
34 714 acheteurs et les mêmes effectifs sur les sept segments.

Deux calculs sont descendus en SQL : le **classement ABC** de
`gold_performance_produit` (une fonction de fenêtrage) et les **règles
d'association** de `gold_affinites_produits`, calculées une fois par construction.

---

## La console SQL

L'onglet Entrepôt affiche la requête de chaque table ; elle se modifie et se
rejoue (`Ctrl` + `Entrée`), avec des exemples prêts à adapter.

| Barrière | Ce qu'elle arrête |
| --- | --- |
| Transaction en **lecture seule** | Toute écriture, refusée par PostgreSQL lui-même. |
| **Délai** de 5 secondes | Une jointure coûteuse sur les consultations, avant qu'elle ne bloque le pool. |
| Examen du **plan** | Tables lues relevées par `EXPLAIN` : une CTE, sous-requête ou jointure vers `public.users` est refusée. |
| Contrôle de **forme** | Une instruction, `SELECT` ou `WITH`, sans mot-clé d'écriture hors chaînes et commentaires. |
| **Authentification** | Route `/admin`, `is_admin` vérifié côté serveur. |

S'y ajoute une limite de douze requêtes par minute. Schémas lisibles : `bronze`,
`silver`, `gold`, `externe`, `controles`. `public` reste fermé : il porte les
condensats de mots de passe et les coordonnées des clients.

Le compte de démonstration, dont les identifiants sont publics, ne lit que `gold`,
`externe` et `controles` : bronze et silver gardent une ligne par client (ville,
année de naissance), trop proche d'une personne pour un accès ouvert à tous.

---

## Orchestration

La chaîne est un **graphe d'actifs Dagster** (`orchestration/`) : deux extractions
Python et 27 modèles dbt, de la table écrite par l'API jusqu'à l'agrégat.

```bash
cd hanabi-dwh && .venv/Scripts/dagster dev
```

Interface sur `http://localhost:3000`.

### Pourquoi Dagster

Les étapes étaient listées à la main dans le workflow GitHub, sans
`ingestion/sources.py` : `externe.taux_change` et `externe.jours_feries` n'étaient
rechargées qu'à la main, alors que `sources.yml` déclare une source périmée au bout
de dix jours. Désormais `brz_taux_change` dépend de l'extraction et l'ordre se
déduit du graphe.

Ce que le graphe apporte aussi :

- **Échecs localisés.** Si Frankfurter ne répond pas, seul l'aval de
  `brz_taux_change` s'arrête.
- **Rattrapage par partitions mensuelles.** Relancer un mois se fait depuis
  l'interface ; l'`INSERT … ON CONFLICT` de `ingestion/sources.py` rend l'opération
  sûre. Un mois coûte un appel à la source, contre trente au jour.
- **Tests attachés aux modèles.** 103 des 120 assertions deviennent des contrôles
  d'actifs avec historique ; les 17 autres (14 sur des sources, 3 réconciliations
  entre plusieurs modèles) tournent dans `dbt build`.
- **Lignage de bout en bout**, depuis les tables de `public`.

Ce qu'il n'apporte pas :

- **La planification.** Sans daemon hébergé, le calendrier de
  `orchestration/planification.py` ne tourne que sous `dagster dev`. En ligne,
  `.github/workflows/entrepot.yml` déclenche à 5 h UTC et appelle le graphe.
- **De la vitesse.** 27 modèles, une minute de construction.
- **La légèreté.** Une soixantaine de paquets, et `dbt-core` ramené à 1.11, borne
  haute de `dagster-dbt`.

### Une exécution

```
29 actifs matérialisés
107 contrôles joués, 0 en échec
dbt : PASS=148 WARN=0 ERROR=0 SKIP=0
```

107 contrôles : 103 assertions dbt et les 4 contrôles de volume et de fraîcheur.
148 nœuds dbt : 27 modèles, 120 assertions et le crochet qui repose les droits. La
somme des commandes facturées de `public.orders` et le total de `gold_kpi_mensuel`
tombent au centime près. Une construction dure une trentaine de secondes sur un
PostgreSQL local rempli de 20 000 comptes.

### Contrôles de volume et de fraîcheur

Les tests dbt vérifient la forme des données. `orchestration/controles.py` vérifie
qu'elles arrivent et qu'elles ne disparaissent pas, après chaque construction :

| Contrôle | Rattaché à | Attendu | Gravité |
|---|---|---|---|
| Commandes jamais en baisse | `slv_commandes` | au moins le plus haut déjà relevé | bloquant |
| Un jour par jour | `gold_ca_quotidien` | une ligne par jour, sans trou, jusqu'à aujourd'hui | bloquant |
| Dernière vente | `gold_ca_quotidien` | une vente dans les 3 derniers jours | alerte |
| Dernier taux de change | `brz_taux_change` | une cotation dans les 5 derniers jours | alerte |

Le premier contrôle repose sur un fait de l'application : une commande n'est
jamais supprimée, l'effacement RGPD l'anonymise. Un contrôle bloquant en échec fait
échouer l'exécution, donc le workflow. Une alerte reste visible sans rien arrêter.

L'instance Dagster de GitHub Actions ne survit pas à l'exécution : chaque résultat
est aussi écrit dans `controles.journal`, que l'onglet Entrepôt du back-office
affiche et que la console SQL peut lire. Après une remise à zéro voulue de la base,
le plus haut relevé ne vaut plus rien :

```sql
delete from controles.journal where controle = 'commandes_jamais_en_baisse';
```

Les verdicts se testent sans base :

```bash
cd hanabi-dwh && .venv/Scripts/python -m unittest discover -s tests/orchestration
```

### Le déclenchement

`.github/workflows/entrepot.yml` tourne chaque jour à 5 h UTC et à la demande. Il
compile le projet, joue `dbt source freshness` (non bloquant) et matérialise les 29
actifs sur la partition du mois en cours. `manifest.json` et `run_results.json` sont
conservés 30 jours.

Lancé à la main, il propose une case « Reconstruire aussi les modèles incrémentaux
depuis zéro » (`dbt build --full-refresh`). Elle répare une table dont les jours
sortis de la fenêtre de rattrapage ont été mal écrits.

L'intégration continue construit l'entrepôt sur un PostgreSQL jetable, rempli par
l'API avec 20 000 comptes de démonstration, puis le reconstruit : ce second passage
incrémental doit tenir les mêmes 120 assertions.

Le workflow ne fait rien tant que le secret `DWH_DATABASE_URL` n'est pas posé : la
tâche s'arrête avec une note, sans échec. Ce secret confie une chaîne de connexion
en écriture à GitHub Actions ; sur des données réelles, on créerait un rôle limité à
la lecture de `public` et à l'écriture dans les schémas de l'entrepôt.

GitHub désactive les tâches planifiées après soixante jours sans activité sur le
dépôt.

### Sans Dagster

```bash
cd hanabi-dwh && .venv/Scripts/python -m ingestion.sources tout && .venv/Scripts/python dwh.py build
```

Dagster ne réimplémente pas dbt : il lance `dbt build` et lit son flux d'événements.

---

## Tests

`dbt build` joue 120 assertions : unicité, non-nullité, intégrité référentielle,
valeurs acceptées, intervalles, unicité de combinaisons, trois réconciliations et
une équivalence entre construction incrémentale et construction complète.

`macros/tests.sql` définit `intervalle` et `combinaison_unique` au lieu d'ajouter
`dbt_utils`. `combinaison_unique` couvre les clés composées des tables d'agrégats,
`(cohorte, décalage)` ou `(produit A, produit B)`, là où une jointure duplique des
lignes sans fausser visiblement les totaux.

### Réconciliations

`tests/assert_ca_reconcilie.sql` vérifie que trois calculs du chiffre d'affaires
(série mensuelle, segmentation, silver) donnent le même nombre.
`tests/assert_segments_reconcilient.sql` vérifie que les segments totalisent la
table des clients, à un écart près : les commandes invitées, que la segmentation
exclut, et dont le montant doit correspondre exactement.
`tests/assert_categories_reconcilient.sql` vérifie que les familles totalisent les
produits. Les deux tables lisent les mêmes lignes, l'une par catégorie figée à
l'achat, l'autre par produit : une famille perdue ou comptée deux fois s'y voit.

Vérification à la main :

```sql
select (select sum(total_cents) from orders where status in ('paid','shipped','delivered')) as source, (select sum(ca_cents) from gold.gold_kpi_mensuel) as entrepot;
```

### Incrémental et complet

`gold_ca_quotidien` compare chaque jour à la moyenne des quatre jours précédents de
même nature. En incrémental, la moyenne se calculait dans la fenêtre de 30 jours
reconstruite, sans voir les jours d'avant : le premier jour de chaque nature sortait
sans référence, les trois suivants avec une moyenne sur trop peu de jours. Chaque
nuit, le jour le plus ancien de la fenêtre était réécrit ainsi une dernière fois,
puis figé : tout jour sorti de la fenêtre gardait une référence fausse. La
construction complète, elle, était juste, et aucune assertion ne portait sur cette
colonne.

Relevé sur une base de démonstration, après un seul passage incrémental :

| jour | nature | écrit | attendu |
| --- | --- | ---: | ---: |
| 24 août 2026 | ouvré | vide | 3 639,25 € |
| 25 août 2026 | ouvré | 4 083,20 € | 3 605,68 € |
| 29 août 2026 | week-end | vide | 2 995,53 € |
| 30 août 2026 | week-end | 3 181,10 € | 3 283,93 € |

La moyenne se calcule désormais sur un an de contexte, puis seule la fenêtre est
écrite. `tests/assert_reference_quotidienne.sql` recalcule la référence sur la table
entière et exige la même valeur ; la CI le joue après une construction complète puis
une construction incrémentale. Une table déjà faussée ne se répare pas par
l'incrémental, qui ne réécrit que sa fenêtre : il faut une reconstruction complète.

---

## Conventions

Le SQL de l'entrepôt ne vise que PostgreSQL : `date_trunc`, `to_char`,
`generate_series`, `filter (where …)` et fenêtrage y sont libres, contrairement à
`analytics.py`.

Noms de modèles et de colonnes en français à partir de silver ; bronze garde les
noms de `models.py`.

Montants en **centimes entiers**, suffixe `_cents`. L'API déduit le format de chaque
colonne de son nom, et l'interface l'affiche en conséquence.
