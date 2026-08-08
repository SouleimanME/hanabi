# hanabi-dwh - entrepôt décisionnel

Projet dbt qui construit, dans la base PostgreSQL de la boutique, trois schémas
en architecture dite **médaillon** : `bronze`, `silver`, `gold`. Le back-office
lit le schéma `gold` par l'onglet **Entrepôt**, et n'y fait qu'un
`SELECT … LIMIT`.

```
public (écrit par l'API)
   └─ bronze   vues, aucune transformation
        └─ silver   nettoyé, conformé, typé
             └─ gold   une table d'agrégats par question métier
                  └─ /admin/warehouse → onglet « Entrepôt »
```

---

## Pourquoi

`hanabi-back/app/analytics.py` répond déjà à toutes ces questions, et continue
de le faire. Les deux chemins coexistent volontairement, parce qu'ils ne
racontent pas la même chose :

| | `analytics.py` | l'entrepôt |
| --- | --- | --- |
| Source | base transactionnelle | instantané daté |
| Fraîcheur | l'instant | dernière construction |
| Coût de lecture | plusieurs agrégations | un `SELECT … LIMIT` |
| Règles métier | écrites en Python, parfois répétées | écrites une fois, en SQL, dans silver |

Un entrepôt construit par lots est **toujours** en retard sur la base. Le
problème n'est pas ce retard, c'est de ne pas savoir de combien : d'où
`gold.gold_execution`, dont l'horodatage est affiché en permanence dans
l'interface.

**Ce que cette architecture n'apporte pas ici.** Neon est un PostgreSQL, donc un
moteur en lignes : sur des volumes analytiques réels, le bon outil serait un
moteur en colonnes (ClickHouse, DuckDB, BigQuery) et Neon ne serait plus que la
source d'ingestion. À l'échelle de cette boutique - une trentaine de milliers de
comptes, une centaine de milliers de consultations - PostgreSQL tient très
largement, et la démarche vaut surtout pour ce qu'elle discipline : une règle
métier écrite une seule fois, des transformations testées, une lignée lisible.
C'est un choix assumé, pas une méconnaissance de la limite.

---

## Construire

```bash
cd hanabi-dwh && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py build
```

`dwh.py` est un lanceur d'une centaine de lignes. Il :

- lit `DATABASE_URL` dans `hanabi-back/.env` si la variable n'est pas déjà dans
  l'environnement - la connexion ne vit qu'à un seul endroit ;
- la découpe en variables `DWH_*` que lit `profiles.yml` (dbt-postgres attend
  cinq champs séparés, pas une URL) ;
- refuse de partir si la base visée n'est pas PostgreSQL ;
- **affiche l'hôte visé avant de commencer.** Construire l'entrepôt dans la base
  de production en croyant viser un conteneur local est l'erreur que ce rappel
  évite.

Autres commandes :

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py test
```

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run -s gold
```

Pour viser une autre base que celle de l'API, exporter `DWH_DATABASE_URL` :
elle l'emporte sur `DATABASE_URL`.

### Sur une base jetable

```bash
docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=hanabi -e POSTGRES_DB=hanabi --name hanabi-pg postgres:16
```

C'est le repli par défaut de `profiles.yml` : `dbt` lancé directement, sans
passer par `dwh.py`, vise ce conteneur et non une base distante.

**La construction ne touche jamais au schéma `public`.** Elle le lit, et n'écrit
que dans `bronze`, `silver` et `gold`. Pour tout défaire :
`drop schema bronze, silver, gold cascade;`.

### Droits de lecture

Un schéma créé par PostgreSQL n'accorde rien à personne : seul son propriétaire
peut le traverser. Les trois schémas étaient donc invisibles depuis la console
Neon et depuis tout client connecté avec un autre rôle - un « permission denied
for schema gold » qui ressemble à une panne alors que c'est le défaut du moteur.
Le schéma `public` échappe à ce piège parce que PostgreSQL lui accorde `USAGE` à
tous dès sa création.

`macros/droits.sql` accorde donc `usage` sur les trois schémas et `select` sur
leurs tables, plus les mêmes droits par défaut sur les tables à venir. **Aucun
droit d'écriture, à aucun moment** : l'entrepôt se reconstruit, il ne se modifie
pas.

La macro est appelée en `on-run-end`, et pas une fois à la main : `dbt run`
recrée les tables gold, et une table recréée perd les droits accordés à la
précédente. Un `GRANT` joué une seule fois se serait défait à la construction
suivante, silencieusement.

Pour les reposer sans reconstruire :

```bash
cd hanabi-dwh && .venv/Scripts/python dwh.py run-operation accorde_lecture
```

---

## Les trois couches

### bronze - 9 vues

Les tables de l'application, nommées sous une forme stable, plus les deux
sources externes chargées dans `externe`. Aucune transformation, aucune donnée
recopiée : le schéma `public` où écrit l'API tient lieu de zone
d'atterrissage.

Deux choses en sortent volontairement :

- **`password_hash`.** Un condensat de mot de passe n'a aucun usage analytique
  et n'a rien à faire dans un schéma que le back-office peut interroger.
- **les visuels** (`art`, `images`). Une photo encodée en base64 pèse plusieurs
  centaines de milliers de caractères et ne répond à aucune question.

Les colonnes sont énumérées plutôt que reprises par `select *`. Une colonne
ajoutée à `users` ne se propage donc pas silencieusement : il faut passer par
bronze, donc décider si elle a sa place ici.

### silver - 7 modèles

Données nettoyées, typées, conformées. C'est ici que vivent les règles métier,
écrites **une seule fois** :

- `slv_commandes.est_ca` porte la règle du chiffre d'affaires, que l'API répète
  sous forme de `status in (…)` dans une quinzaine de requêtes ;
- `slv_lignes_commande` porte la marge, calculée sur le prix et le coût **figés
  à l'achat** - un changement de tarif fournisseur ne doit pas réécrire le
  résultat des mois déjà clos ;
- `slv_clients` porte l'âge et la tranche d'âge, déduits de la seule année de
  naissance, exactement comme `analytics.py`. Le raccourci est reproduit à
  dessein : deux découpages différents pour la même population donneraient deux
  histogrammes contradictoires ;
- `slv_calendrier_mensuel` garantit qu'un mois sans commande apparaît à zéro
  plutôt que de disparaître d'une série ;
- `slv_calendrier_quotidien` fait de même au jour près, et porte les trois
  décisions liées aux sources externes : le taux de change est reporté sur les
  jours non cotés, les fériés français et japonais restent deux colonnes
  distinctes, et seuls les fériés nationaux comptent.

Tout est en vues, sauf `slv_lignes_commande`, matérialisée en table : sept
modèles gold s'appuient dessus, et en vue la jointure serait rejouée sept fois.

### gold - 11 tables

Une par question métier. C'est la seule couche que l'API interroge.

| Table | Question |
| --- | --- |
| `gold_kpi_mensuel` | Comment le chiffre d'affaires, la marge et l'audience évoluent-ils mois par mois ? |
| `gold_performance_produit` | Quelles références rapportent, lesquelles font du volume sans marge ? |
| `gold_performance_categorie` | Quelle famille du catalogue porte le résultat ? |
| `gold_segments_rfm` | Comment la clientèle se répartit-elle, et quelle part du chiffre chaque segment pèse-t-il ? |
| `gold_clients_rfm` | Qui sont les clients derrière chaque segment ? |
| `gold_cohortes_retention` | Les clients recrutés un mois donné reviennent-ils ? |
| `gold_demographie_clients` | Ville, âge, civilité : quels profils achètent, et pour combien ? |
| `gold_promotions` | Quels codes font entrer du chiffre, lesquels n'ont jamais servi ? |
| `gold_affinites_produits` | Quels articles s'achètent ensemble plus souvent que le hasard ne le voudrait ? |
| `gold_ca_quotidien` | Cette journée est-elle mauvaise, ou simplement fériée ? Et la marge bouge-t-elle à cause des prix ou du yen ? |
| `gold_execution` | De quand datent ces chiffres ? |

### La notation RFM, et pourquoi elle a changé

Les scores R, F et M sont des **quintiles de population** : « 5 » veut dire
« parmi les 20 % de clients les mieux placés ».

Ce n'était pas le cas au départ. Le classement portait sur les *valeurs
distinctes* - une garantie que deux clients au même montant soient notés pareil,
ce qui est indispensable, mais qui décalait le sens du mot quintile. Avec 679
anciennetés différentes étalées sur deux ans, un score de récence à 5 signifiait
« dans les 136 premières valeurs de l'échelle », pas « parmi les 20 % les plus
récents ». La clientèle étant concentrée sur les achats récents :

| | avant | après |
| --- | ---: | ---: |
| clients notés R=5 | 73 % | 19,9 % |
| segment « À risque » | 19 clients (0,1 % du CA) | 5 430 clients (23,1 % du CA) |

Le segment où une relance a le plus de valeur - des clients qui ont déjà prouvé
qu'ils achetaient et ne reviennent plus - était réduit à dix-neuf personnes par
un artefact de calcul.

La correction note chaque valeur par le **rang médian de son groupe d'ex aequo**,
exprimé en part de la population (`cume_dist()` moins la demi-largeur du groupe).
Les deux exigences tiennent ensemble : les ex aequo partagent leur score, et le
découpage porte sur la population.

**Limite qui demeure** : un groupe d'ex aequo plus gros qu'un quintile ne peut pas
être réparti. 64,9 % des clients n'ont commandé qu'une fois, donc partagent le
même score F - c'est une propriété de la donnée, qu'aucune méthode de notation ne
lève.

Ce calcul existe en double, ici et dans `_score_par_rang` de
`hanabi-back/app/analytics.py`. **Les deux doivent rester identiques** : ils
notent la même clientèle, et une divergence afficherait deux segmentations
contradictoires selon l'onglet ouvert. La vérification est directe - les deux
chemins produisent aujourd'hui exactement les mêmes scores pour les 34 714
acheteurs, et les mêmes effectifs sur les sept segments.

Deux calculs y ont gagné à descendre en SQL :

- le **classement ABC** de `gold_performance_produit`, qui demandait un tri
  Python sur tout le catalogue, tient dans une fonction de fenêtrage ;
- les **règles d'association** de `gold_affinites_produits`, dont
  `analytics.py` signalait lui-même qu'elles devraient « redescendre en SQL,
  voire dans une table précalculée » sur un catalogue plus fourni. C'est fait,
  une fois par construction, plutôt qu'à chaque ouverture du tableau de bord.

---

## Interroger l'entrepôt soi-même

Le back-office expose une **console SQL** dans l'onglet Entrepôt : la requête
affichée est modifiable et rejouable (`Ctrl` + `Entrée`). C'est ce qui sépare un
entrepôt d'un tableau de bord de plus - la question qu'on se pose devant un
agrégat est presque toujours « et si je filtrais autrement ? ».

Ouvrir une saisie SQL libre dans une interface web est une décision qui se pèse.
Elle est refermée par **cinq barrières indépendantes**, aucune n'étant le seul
rempart :

| Barrière | Ce qu'elle arrête |
| --- | --- |
| Transaction en **lecture seule** | Toute écriture, quelle que soit la requête. C'est PostgreSQL qui refuse, pas notre analyse : la seule barrière à laquelle on fait vraiment confiance. |
| **Délai** de 5 secondes | Une jointure malheureuse sur les 700 000 consultations, interrompue au lieu de bloquer une connexion du pool. |
| Examen du **plan d'exécution** | Les tables réellement lues sont demandées à `EXPLAIN`, pas devinées. Une fuite vers `public.users` par CTE, sous-requête ou jointure est refusée. |
| Contrôle de **forme** | Une seule instruction, commençant par `SELECT` ou `WITH`, sans mot-clef d'écriture. |
| **Authentification** | Route `/admin`, `is_admin` vérifié côté serveur. |

Les schémas ouverts sont `bronze`, `silver` et `gold`. **`public` en est exclu** :
c'est là que vivent les condensats de mots de passe, et l'entrepôt expose déjà
tout ce qui a un usage analytique.

Le contrôle de forme ignore les mots-clefs situés dans une chaîne ou un
commentaire : filtrer sur la valeur `'Delete me'` est légitime, et un refus
incompréhensible vaut moins qu'un refus qui n'arrive pas.

La console reste ouverte au compte vitrine en lecture seule, et c'est cohérent :
elle ne peut rien modifier, et interroger l'entrepôt soi-même est précisément ce
qu'un visiteur vient voir.

---

## Orchestration

La chaîne est déclarée comme un **graphe d'actifs Dagster**, dans
`orchestration/`. Deux extractions Python et 27 modèles dbt y forment un seul
graphe, de la table écrite par l'API jusqu'à l'agrégat lu par le back-office.

```bash
cd hanabi-dwh && .venv/Scripts/dagster dev
```

L'interface s'ouvre sur `http://localhost:3000`.

### Le défaut que ça corrige

Avant, les étapes étaient énumérées à la main dans le workflow GitHub. Et
`ingestion/sources.py` n'y figurait pas : `externe.taux_change` et
`externe.jours_feries` n'étaient rechargées que lorsque quelqu'un y pensait,
alors que `sources.yml` déclare une source périmée au bout de dix jours. Bronze
lisait deux tables que rien n'alimentait.

Une étape manquante dans une liste écrite à la main ne se voit pas. Une
dépendance manquante dans un graphe, si : `brz_taux_change` **déclare** dépendre
de l'extraction, et l'ordre d'exécution se déduit de cette déclaration au lieu
d'être retranscrit ailleurs. Ajouter une source demain ne demandera pas de se
souvenir qu'il fallait la placer avant `dbt build`.

### Ce que le graphe apporte en plus

**Un échec cesse d'être binaire.** Si Frankfurter ne répond pas, seuls
`brz_taux_change` et son aval s'arrêtent ; les autres modèles se construisent.
Le cron, lui, échouait en entier.

**La série de taux se rattrape.** Elle est découpée en partitions mensuelles.
Dagster sait quels mois sont chargés, et relancer un mois manquant est une
action dans l'interface, pas un script à retrouver. L'`INSERT … ON CONFLICT`
d'`ingestion/sources.py` était déjà idempotent - c'est lui qui rend le
rattrapage sûr, le partitionnement ne fait que le rendre accessible.

Le mois est la bonne maille et non le jour : la source accepte une plage, et un
mois coûte un appel là où trente jours en coûteraient trente, sur un service
public et gratuit.

**Les tests se lisent sur le modèle qu'ils vérifient.** Sur les 112 assertions
dbt, 96 deviennent des contrôles d'actifs, avec leur historique - « depuis quand
ce test échoue-t-il ? » se lit au lieu de se chercher. Les 16 autres (14 portant
sur une source, 2 tests singuliers, qui ne se rattachent à aucun modèle unique)
continuent de tourner dans `dbt build` sans apparaître comme contrôles.

**Le lignage traverse les outils.** `dbt docs` s'arrête au bord du projet dbt.
Le graphe Dagster part des sept tables de `public`, montre qu'elles sont écrites
par l'API et non par la chaîne, et va jusqu'à `gold_execution`.

### Ce que Dagster n'apporte pas ici

**Rien côté planification.** Un calendrier Dagster suppose un daemon qui tourne
en permanence, et rien n'en héberge un : celui déclaré dans
`orchestration/planification.py` ne s'exécute que quand `dagster dev` est
ouvert. En ligne, **c'est toujours `.github/workflows/entrepot.yml` qui donne
l'heure** - à 5 h UTC, la même que le calendrier Dagster - mais il appelle
désormais le graphe au lieu de redire les étapes. La planification vit à deux
endroits, l'enchaînement à un seul, et c'est l'enchaînement qui se serait
désynchronisé.

**Aucun gain de vitesse.** 27 modèles, une base, une minute de construction. Le
parallélisme et les reprises de Dagster sont dimensionnés pour bien plus gros.

**Un coût réel.** Une soixantaine de paquets sur un projet qui revendique des
listes courtes, et `dbt-core` redescendu de 1.12 à 1.11, borne haute de
`dagster-dbt`. Aucun modèle n'emploie de nouveauté de la 1.12, et le pas en
arrière aligne enfin le cœur sur l'adaptateur, resté en 1.11.

À cette échelle, seul le premier point - l'extraction orpheline - justifierait
l'outil à lui seul. Le reste est réel mais modeste, et c'est dit ici plutôt que
maquillé.

### Le déclenchement

`.github/workflows/entrepot.yml` s'exécute **chaque jour à 5 h UTC** et à la
demande depuis l'onglet Actions. Il compile le projet dbt, joue
`dbt source freshness` (non bloquant), puis matérialise les 29 actifs sur la
partition du mois en cours. Les artefacts `manifest.json` et `run_results.json`
sont conservés 30 jours, y compris en cas d'échec.

**Le workflow est inerte tant que le secret `DWH_DATABASE_URL` n'est pas
renseigné** dans les paramètres du dépôt. Sans lui, la tâche s'arrête avec une
note explicative plutôt que d'échouer en rouge : un fork n'a pas à afficher une
CI cassée pour une base à laquelle il n'a pas accès.

Avant de le renseigner, mesurer ce que ça implique : c'est confier une chaîne de
connexion en écriture à GitHub Actions. Sur une base de démonstration c'est
acceptable ; sur des données réelles, on créerait un rôle PostgreSQL dédié,
limité à la lecture de `public` et à l'écriture dans les schémas de l'entrepôt.

### Construire sans Dagster

Rien n'a été retiré. `dwh.py` et `ingestion/sources.py` restent utilisables
seuls, et c'est toujours le chemin le plus court sur un poste :

```bash
cd hanabi-dwh && .venv/Scripts/python -m ingestion.sources tout && .venv/Scripts/python dwh.py build
```

Dagster ne réimplémente pas dbt : il lance `dbt build` et lit son flux
d'événements pour savoir quel modèle vient d'être construit et quels tests ont
porté dessus.

---

## Tests

`dbt build` joue 112 assertions après avoir construit les modèles : unicité,
non-nullité, intégrité référentielle, valeurs acceptées, intervalles, unicité de
combinaisons, et deux réconciliations croisées.

Deux tests génériques sont définis dans `macros/tests.sql` plutôt qu'empruntés
au paquet `dbt_utils` : `intervalle` et `combinaison_unique`. Quinze lignes à
écrire contre une dépendance à télécharger et à suivre - le jour où il en
faudrait dix, le paquet redeviendrait le bon choix.

Le plus utile est `combinaison_unique` : le test `unique` de dbt ne porte que
sur une colonne, or la clef d'une table d'agrégats est presque toujours composée
- `(cohorte, décalage)`, `(produit A, produit B)` - et c'est exactement là que
se glisse le doublon, quand une jointure duplique des lignes sans qu'aucun total
ne paraisse aberrant.

### Les réconciliations croisées

`tests/assert_ca_reconcilie.sql` et `tests/assert_segments_reconcilient.sql` sont
des tests *singuliers* : du SQL libre qui passe quand il ne renvoie aucune ligne.
Ils vérifient que trois chemins de calcul du chiffre d'affaires - la série
mensuelle partie du calendrier, la segmentation partie des clients, la couche
silver partie des commandes - tombent sur le même nombre, et que la table des
segments totalise exactement la table des clients.

C'est le contrôle qu'on fait à la main la première fois, puis qu'on oublie de
refaire. Un tableau de bord où la somme des segments ne fait pas le total perd
toute crédibilité, et la divergence ne se voit pas à l'œil : il faut la chercher.

Le second teste une égalité **avec un écart attendu non nul** : la segmentation
exclut les commandes invitées, non rattachées à un compte. La différence doit
valoir exactement le montant de ces commandes - la confondre avec une erreur de
calcul serait le contresens le plus facile à commettre ici.

### Le vérifier à la main

```sql
select (select sum(total_cents) from orders where status in ('paid','shipped','delivered')) as source, (select sum(ca_cents) from gold.gold_kpi_mensuel) as entrepot;
```

---

## Conventions

Le SQL de l'entrepôt **n'a pas à être portable**, contrairement à celui de
`analytics.py` : il ne vise que PostgreSQL. `date_trunc`, `to_char`,
`generate_series`, `filter (where …)` et les fonctions de fenêtrage y sont donc
employés librement - c'est d'ailleurs l'une des raisons pour lesquelles ces
calculs sont plus courts ici.

Les noms de modèles et de colonnes sont en français à partir de silver, comme le
reste du back-office. Bronze garde les noms de la source : c'est ce qui rend la
correspondance avec `models.py` immédiate.

Les montants restent des **entiers de centimes**, suffixe `_cents` obligatoire.
Le formatage en euros se fait à l'affichage - l'API annonce le type de chaque
colonne, déduit de son nom, et l'interface s'en sert.
