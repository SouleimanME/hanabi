# Hanabi 花火

Boutique en ligne fictive d'objets japonais, avec sa chaîne de données : la
boutique produit les événements, un entrepôt dbt les transforme, le back-office
lit les agrégats.

La boutique sert d'abord de source : 100 000 comptes, 59 000 commandes, 90 000
lignes de commande et 700 000 consultations de fiche à modéliser.

Conçu et développé par Souleiman MECHERI.

[Voir le site](https://hanabi-6x9.pages.dev) ·
[Back-office](https://hanabi-6x9.pages.dev/admin) ·
[L'entrepôt en détail](hanabi-dwh/README.md)

![Page d'accueil de la boutique Hanabi](docs/accueil.jpg)

> Boutique fictive, sans activité commerciale. Aucun paiement n'est encaissé et
> aucune commande n'est expédiée.

---

## Aperçu

**Direction artistique.** Deux matières, la laque noire et le vermillon, plus le
papier washi pour le thème clair. Chaque objet est représenté par un blason
dessiné en SVG, sur la grammaire des kamon : même grille, même épaisseur de coupe.
Titres en Shippori Mincho, texte en Manrope.

Panier en tiroir, avec code promo, jauge de livraison offerte, date de livraison
estimée et total recalculé par le serveur.

![Panier ouvert sur la page d'accueil](docs/panier.jpg)

Le thème suit le réglage du système jusqu'au premier choix, qui est mémorisé.

![La page d'accueil en thème clair](docs/theme-clair.jpg)

Sur téléphone, la navigation passe dans un menu en tiroir.

<img src="docs/mobile.jpg" alt="Plateau d'objets et menu en tiroir sur téléphone" width="440">

Le back-office reprend la même charte, en plus dense. L'onglet Entrepôt montre
les trois couches, la fraîcheur de la dernière construction, chaque table
d'agrégats avec la question qu'elle traite, et une console SQL en lecture seule.

![Onglet Entrepôt du back-office](docs/entrepot.jpg)

---

## La chaîne de données

```
public                 ┐
tables applicatives    │   bronze            silver             gold
écrites par l'API      ├→  9 vues        →   7 modèles      →   11 tables
                       │   aucune            règles métier      une par
externe                │   transformation    écrites une fois   question
2 sources publiques    ┘                                            ↓
BCE et jours fériés                                     back-office + boutique
```

27 modèles dbt, 111 tests, déclarés comme un graphe d'actifs Dagster et
reconstruits chaque jour. Le détail est dans
[hanabi-dwh/README.md](hanabi-dwh/README.md).

**Bronze en vues, colonnes énumérées.** Rien n'est dupliqué, et une colonne
ajoutée à `users` n'entre dans l'entrepôt que si on l'y fait entrer. Le condensat
des mots de passe, les photos en base64 et les coordonnées des clients (nom,
e-mail, téléphone, adresses) restent dehors : un client s'y désigne par son
identifiant.

**Règles métier en silver, écrites une fois.** La définition du chiffre
d'affaires, répétée dans quinze requêtes de l'API, tient dans une colonne
`est_ca`.

**Marge figée à l'achat.** Prix et coût unitaires sont copiés dans la ligne de
commande : un nouveau tarif fournisseur ne réécrit pas les mois clos.

**Séries construites sur le calendrier.** Un mois sans commande sort à zéro au
lieu de disparaître de la courbe.

`dbt build` construit et teste dans l'ordre du graphe : un test en échec bloque
l'aval. Les 111 assertions couvrent unicité, non-nullité, intégrité
référentielle, valeurs acceptées et intervalles. Deux sont des réconciliations :
trois calculs du chiffre d'affaires doivent donner le même nombre, et la table
des segments doit totaliser celle des clients.

### Un défaut que les tests laissaient passer

Les scores RFM classaient les valeurs distinctes au lieu de la population. Avec
679 anciennetés sur deux ans, « récence 5 » voulait dire « dans les 136
premières valeurs », et non « parmi les 20 % de clients les plus récents ».
Toutes les assertions passaient.

| | avant | après |
| --- | ---: | ---: |
| clients notés R=5 | 73 % | 19,9 % |
| segment « À risque » | 19 clients, 0,1 % du CA | 5 430 clients, 23,1 % du CA |

Chaque valeur est désormais notée au rang médian de son groupe d'ex aequo,
exprimé en part de population.

### Réseau, concurrence, paiement

**Commande idempotente.** Le navigateur tire une clé avant l'envoi et la répète
en cas de réessai ; le serveur stocke la clé avec sa réponse et la rejoue. L'unicité
repose sur une contrainte de base : un `SELECT` préalable laisserait passer la
seconde requête d'un double envoi.

**Courriel écrit dans la transaction de la commande** (*transactional outbox*).
Une tâche de fond le remet ensuite avec des réessais espacés : une panne du relais
ne fait plus échouer un achat payé. Remise au moins une fois.

**Paiement simulé, échecs jouables.** Le cas délicat est l'issue indécise : un
délai dépassé ne dit pas si le débit a eu lieu. La commande reste alors en attente
de rapprochement, stock retenu, réponse 202. Une première version annulait tout ;
l'annulation emportait la ligne d'idempotence, et le second débit redevenait
possible.

**Stock.** Décrément par `UPDATE ... WHERE stock >= qty` et contrainte
`CHECK (stock >= 0)`. Le test lance douze fils d'exécution derrière une barrière
de départ sur le même article : une seule commande passe.

### Le compte

Informations, cartes enregistrées, mot de passe et adresse de connexion.

- **Aucun numéro ni cryptogramme en base** : réseau, quatre derniers chiffres,
  expiration et jeton opaque du prestataire. Le navigateur n'envoie rien d'autre,
  un test le vérifie sur le fil.
- **Mot de passe courant exigé** pour changer ce qui donne accès au compte. La
  nouvelle adresse repart non confirmée.
- **Seuls les champs modifiés partent**, pour ne pas écraser un autre onglet.
- **Aucun identifiant de compte dans les routes** : elles agissent sur le porteur
  du jeton. La carte d'un autre rend 404.

### Effacement et portabilité

Un client peut exporter ses données et supprimer son compte. La suppression
anonymise : le Code de commerce impose de garder dix ans les pièces comptables, ce
que le RGPD prévoit (art. 17-3-b).

| | |
| --- | --- |
| Effacé | moyens de paiement, jetons, alertes de stock, abonnement, courriels en file, adresses de livraison |
| Conservé, délié | commandes et montants, texte des avis, volume de navigation |

L'adresse de remplacement est en `.invalid` (RFC 2606) et le condensat devient une
valeur que bcrypt ne produit jamais. Le test parcourt toutes les colonnes
textuelles du schéma à la recherche des valeurs personnelles : une table oubliée
dans `rgpd.anonymiser` le fait échouer.

### Parcours de bout en bout

Douze parcours Playwright contre une vraie API sur un SQLite jetable, barrières
anti-robots actives. Le plus utile vérifie qu'après une coupure réseau, le réessai
porte la même clé d'idempotence que la première tentative. Un autre paie avec la
carte de test `4000 0000 0000 0002` et attend le refus de la banque : le numéro
reste dans le navigateur, seul le jeton qu'il désigne part au paiement simulé.

### Courriels promis, courriels envoyés

- **Retour en stock** : la demande faite sur la fiche part au réassort (back-office
  ou commande annulée), une fois, dans la langue de la page, puis se ferme.
- **Désinscription** : chaque lettre porte un lien signé (HMAC du numéro
  d'inscription, sans l'adresse dans l'URL) ; un clic suffit.
- **Confirmation de commande** : elle rappelle l'adresse de livraison, gardée sur
  la commande et effacée avec le compte.

### Accessibilité et poids

Couples de couleurs mesurés dans les deux thèmes, 4,5:1 au minimum, y compris le
texte posé sur le vermillon (`--on-accent`) et les cases de la heatmap des
cohortes. Palette des graphiques validée pour les daltonismes courants ; aucun
statut porté par la couleur seule.

`npm run build` échoue si un lot dépasse son budget :

| lot | transféré (gzip) | plafond |
| --- | ---: | ---: |
| `index` (React et le socle) | 45,4 ko | 51 ko |
| `App` (la boutique) | 53,1 ko | 63 ko |
| `Admin` (chargé à la demande) | 25,0 ko | 28 ko |
| CSS | 14,6 ko | 22 ko |

### Exploitation

Chaque requête porte un identifiant, repris dans la réponse et dans des journaux
JSON en production ; les adresses IP y sont tronquées. `/health` fait un
aller-retour jusqu'à la base et répond 503 si elle ne suit pas.

Les courriels sortent par défaut en `.eml` dans `var/courriels/`, message MIME
complet. `MAIL_BACKEND=smtp` bascule sur un vrai relais (voir `.env.example`).
L'onglet Exploitation du back-office affiche la file et les paiements à rapprocher.

### La console SQL

Cinq barrières : transaction en lecture seule, délai de cinq secondes, tables lues
relevées dans le plan `EXPLAIN` (une CTE vers `public.users` est refusée), contrôle
de forme, compte administrateur. Plus une limite de débit, le compte de
démonstration étant public.

### Le compte de démonstration

Ses identifiants sont affichés à la connexion. Il lit tout le back-office et
n'écrit rien, refus posé côté serveur. Toute route qui rend un nom, une adresse
e-mail, une ville ou une adresse de livraison la masque pour lui : clients,
commandes, alertes, tableau de bord, meilleurs clients, segments RFM. L'entrepôt ne
copie aucune coordonnée (un client y est un identifiant), et la console ne lui
ouvre que les agrégats (`gold`).

### L'entrepôt dans la vitrine

« Souvent achetés ensemble » lit `gold_affinites_produits`, trié par lift et limité
aux paires au-dessus de 1.

### Orchestration

Deux extractions Python et 27 modèles dbt forment un seul graphe Dagster. Avant,
les étapes étaient listées à la main dans le workflow et l'extraction des taux
n'y figurait pas : bronze lisait une table que rien n'alimentait. Désormais
`brz_taux_change` dépend de l'extraction et l'ordre se déduit du graphe. Un échec
n'arrête que l'aval, et la série de taux se rejoue par partition mensuelle.

Sans daemon hébergé, GitHub Actions reste l'horloge et appelle le graphe.

### Limite d'architecture

PostgreSQL est un moteur en lignes. À volume analytique réel, le médaillon irait
dans un moteur en colonnes (ClickHouse, DuckDB, BigQuery) et Neon resterait la
source.

---

## En résumé

| Domaine | Réalisations |
| --- | --- |
| Données | Médaillon dbt sur PostgreSQL, 27 modèles, 111 tests, orchestration Dagster par partitions, console SQL bridée |
| Interface | Charte laque et vermillon, blasons SVG, thème clair et sombre, 3 langues, menu en tiroir |
| Achat | Panier persistant, articles gardés, favoris, codes promo, livraison estimée, annulation d'un retrait |
| Back-office | Tableau de bord, analytique (rentabilité, prévisions, cohortes, RFM, affinités), entrepôt, exploitation |
| Sécurité | Anti-robots (preuve de travail en Web Worker, pot de miel, délai de saisie), limitation par compte et par IP, en-têtes durcis |
| Fiabilité | Commande idempotente, outbox transactionnelle, stock concurrent, journal structuré |
| Conformité | Mentions légales, CGV versionnées et acceptées côté serveur, RGPD art. 17 et 20 |
| Accessibilité | Focus piégé dans les fenêtres, clavier, contraste mesuré, `prefers-reduced-motion` |
| Qualité | 452 tests API, 198 tests d'interface, 12 parcours e2e, 111 assertions dbt, 14 tests des contrôles de l'entrepôt, budget de poids |

---

## Stack

React 18 et Vite, sans bibliothèque de composants, de CSS, de routage ni
d'animation. Seule dépendance d'exécution en plus de React : `lucide-react`.

FastAPI, SQLAlchemy 2 et Pydantic v2 ; SQLite en local, PostgreSQL (Neon) en
production ; JWT et bcrypt.

dbt sur PostgreSQL, orchestré par Dagster.

---

## Démarrer en local

Prérequis : Node 20+ et Python 3.11+.

```bash
cd hanabi-back
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

```bash
cd hanabi-front
npm install
npm run dev
```

Boutique sur `http://localhost:5173`, back-office sur `/admin`, documentation de
l'API sur `http://localhost:8000/docs`.

L'entrepôt est facultatif et demande PostgreSQL :

```bash
cd hanabi-dwh
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python dwh.py build
```

Sans entrepôt, l'onglet correspondant affiche la commande à lancer. Le graphe
Dagster s'ouvre sur `http://localhost:3000` :

```bash
cd hanabi-dwh && .venv/Scripts/dagster dev
```

Un client d'essai est créé au démarrage (`demo@hanabi.fr` / `demo1234`).
L'administrateur vient de `ADMIN_EMAIL` et `ADMIN_PASSWORD` ; sans ces variables,
aucun n'est créé.

---

## Tests

```bash
cd hanabi-back && .venv/Scripts/python -m pytest tests/ -q
```

```bash
cd hanabi-front && npm run lint && npm run format:check && npm test && npm run build
```

```bash
cd hanabi-front && npm run e2e
```

```bash
cd hanabi-dwh && .venv/Scripts/dbt parse --profiles-dir . --project-dir . && .venv/Scripts/dagster definitions validate
```

Côté API : prix et remises, stock en concurrence, authentification, anti-robots,
cloisonnement du back-office, export CSV, notation RFM, anonymisation.

Côté interface, les tests visent des propriétés plutôt que des valeurs figées :

- le lissage Fritsch-Carlson des courbes ne dépasse jamais les points mesurés
  (échantillonnage des Bézier produites) ;
- les dictionnaires anglais et espagnol couvrent toutes les clés du français, avec
  les mêmes marqueurs ;
- frais de port et seuil de gratuité sont comparés entre `lib/constants.js` et
  `app/pricing.py`.

Ces tests ont trouvé deux défauts à leur première exécution : `niceTicks` rendait
une graduation haute sous le maximum de la série, et `estimateDelivery` gardait
l'heure de la commande.

---

## Structure

```
hanabi-back/          API FastAPI
  app/
    routers/          points d'entrée HTTP
    pricing.py        calcul des montants
    analytics.py      calculs du back-office sur la base transactionnelle
    warehouse.py      lecture des agrégats dbt, console SQL
    rgpd.py           portabilité et effacement
    idempotency.py    rejeu des requêtes non répétables
    outbox.py         file des courriels
    payments.py       autorisation simulée
    observability.py  identifiant de requête, journal structuré
  tests/

hanabi-front/         Interface React
  src/
    components/ pages/ hooks/ lib/ i18n/
    styles/           charte et CSS par domaine
    admin/            back-office, chargé à la demande
  e2e/                parcours Playwright

hanabi-dwh/           Entrepôt (dbt + Dagster)
  models/bronze/ models/silver/ models/gold/
  ingestion/          sources publiques (BCE, jours fériés)
  orchestration/      graphe d'actifs
```

Conventions et pièges connus : [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Limites connues

- **Paiement non branché.** La carte est validée (Luhn, réseau) mais rien ne
  quitte le navigateur ; un vrai branchement passerait par les composants du
  prestataire.
- **Photos en base64 dans la base.** La réponse du catalogue grossit avec elles ;
  la suite logique est un stockage objet.
- **Reconstruction planifiée conditionnée à `DWH_DATABASE_URL`** dans les secrets du
  dépôt. GitHub désactive aussi les tâches planifiées après soixante jours sans
  activité.
- **Mentions légales à compléter.** Aucune identité d'entreprise n'est inventée.
- **Anti-robots en mémoire du processus.** Plusieurs instances demanderaient Redis.
- **Messages de l'API en français**, quelle que soit la langue de l'interface. Les
  courriels déclenchés depuis une page (lettre, retour en stock) suivent sa langue.
- **Panier et favoris en `localStorage`**, donc propres à un appareil.

---

## Mise en ligne

[DEPLOY.md](DEPLOY.md) : hébergement gratuit, variables d'environnement,
vérifications.

## Auteur

Souleiman MECHERI : conception, interface, API, chaîne de données, sécurité, mise
en ligne.

## Licence

Tous droits réservés, voir [LICENSE](LICENSE). Code consultable pour évaluation ;
reproduction, redistribution, modification et usage commercial soumis à accord
écrit.

Une faille à signaler : [SECURITY.md](SECURITY.md).
