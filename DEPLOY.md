# Mise en ligne

Objectif : une URL publique, gratuite, consultable depuis n'importe quel
appareil. Compter une trentaine de minutes la première fois.

Hanabi se compose de deux projets à héberger séparément :

| Projet | Nature | Hébergeur | Fichier de config |
| --- | --- | --- | --- |
| `hanabi-front` | build statique (Vite) | Cloudflare Pages | `hanabi-front/public/_redirects` |
| `hanabi-back` | service Python (FastAPI) | Render | `render.yaml` |

Le build statique part sur un réseau de cache, sans mise en veille ; l'API a
besoin d'un processus. Le reste de la configuration vit dans ces deux fichiers,
sauf les valeurs secrètes ou connues après le premier déploiement.

---

## 1. Publier le dépôt sur GitHub

Les deux hébergeurs se branchent sur un dépôt Git. Il n'y a pas encore de dépôt
distant.

**Avant tout, vérifier qu'aucun secret ne part :**

```bash
git check-ignore -v hanabi-back/.env
```

La commande doit répondre `.gitignore:25:.env`. Ce fichier contient ta clé de
signature et ton mot de passe administrateur : il ne doit jamais être versionné.
Seul `.env.example`, sans valeurs, l'est.

**Créer le dépôt.** Avec l'outil en ligne de commande GitHub :

```bash
gh repo create hanabi --public --source=. --remote=origin --push
```

Sans cet outil : créer le dépôt sur github.com (bouton **New**, sans README ni
.gitignore puisqu'ils existent déjà, sinon le dépôt aurait un commit et la
première poussée serait refusée), puis :

```bash
git remote add origin https://github.com/<ton-compte>/hanabi.git
git push -u origin main
```

> Un dépôt **public** est nécessaire pour que le portfolio soit consultable, et
> il permet aussi aux hébergeurs de s'y connecter sans autorisation étendue.

Les deux hébergeurs déploient la branche principale, il n'y a donc rien à
fusionner : `main` est la seule branche publiée.

L'intégration continue (`.github/workflows/ci.yml`) se déclenche au premier
envoi : tests de l'API, lint, tests et build de l'interface, analyse du projet
dbt. L'onglet **Actions** doit afficher trois tâches en vert.

---

## 2. La base sur Neon

À faire avant Render : la chaîne de connexion obtenue ici est demandée à l'étape
suivante.

1. Créer un compte sur [neon.com](https://neon.com).
2. **Create project**. Choisir une région proche de celle du service Render
   (`aws-eu-central-1` pour Francfort) : un autre continent ajoute une centaine de
   millisecondes par requête.
3. Dans le panneau **Connect**, copier la chaîne de connexion **directe** :
   celle du format « Connection string », dont le nom d'hôte ne comporte pas
   `-pooler`. L'option **Connection pooling** doit être désactivée, sinon c'est
   la variante mise en commun qui est proposée.

   Le pooler de Neon travaille en mode transaction et perd le réglage de
   session `timezone=utc` posé par `database.py` ; les commandes de fin de mois
   changeraient alors de mois dans les séries. L'API a déjà son propre pool.

La chaîne ressemble à ceci, le mot de passe en clair au milieu :

```
postgresql://neondb_owner:MOT_DE_PASSE@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

Elle se colle dans le tableau de bord Render, et nulle part ailleurs : ni dépôt,
ni capture, ni message.

**Rien à créer côté schéma.** Les tables et les index sont posés par Alembic au
premier démarrage de l'API, puis le jeu de données de démonstration est généré
dans la foulée.

### Ce qu'implique l'offre gratuite de Neon

- 0,5 Go de stockage et 100 CU-heures de calcul par mois.
- **Mise en veille au bout de cinq minutes** sans requête, non désactivable. Le
  réveil prend quelques centaines de millisecondes, et le pool est configuré
  pour le supporter (`pool_pre_ping`).
- Pas de date d'expiration : le projet reste en place tant qu'il est utilisé.

### Sauvegardes et restauration

Neon sauvegarde en continu, et l'offre gratuite permet de **remonter le temps
sur les sept derniers jours** (*point-in-time recovery*).

**Ce que Neon couvre.** Une suppression accidentelle, une migration ratée, un
`UPDATE` sans `WHERE` : on crée une branche à l'instant précédant l'incident,
on vérifie, puis on bascule. Dans la console Neon : *Branches → Create branch →
Time travel*, en choisissant l'horodatage.

**Ce que Neon ne couvre pas.** Un compte fermé, un projet supprimé, ou une
panne du fournisseur emportent aussi les sauvegardes. Une copie hors de chez lui
reste nécessaire dès que les données ont de la valeur.

Copie manuelle, avec la chaîne **directe** (pas celle du *pooler*) :

```bash
pg_dump "$DWH_DATABASE_URL" --format=custom --no-owner --file=hanabi-$(date +%F).dump
```

Restauration dans une base vide :

```bash
pg_restore --dbname="$URL_CIBLE" --no-owner --clean --if-exists hanabi-2026-08-16.dump
```

Tester une fois la restauration sur une branche Neon jetable, en comptant les
lignes.

> Ici la base se reconstruit : catalogue dans `seed.py`, jeu de démonstration
> dans `demo_data.py`. Seules de vraies commandes seraient irremplaçables.

### Savoir que le site est tombé

`/health` fait un aller-retour jusqu'à la base et rend **503** si elle ne répond
pas. Le workflow `.github/workflows/surveillance.yml` la sonde toutes les quinze
minutes. Il échoue si l'API est injoignable, si elle rend autre chose que 200,
ou si elle rend 200 avec `status: degrade`, ce qui arrive quand la remise des
courriels est en panne alors que le site répond normalement.

Pour l'activer, ajouter un secret de dépôt :

| Secret | Valeur |
| --- | --- |
| `API_HEALTH_URL` | `https://ton-api.onrender.com/health` |

Sans ce secret, le workflow s'arrête sans échouer. L'alerte arrive par le
courriel que GitHub envoie à la première exécution en échec.

Limite : les tâches planifiées de GitHub prennent souvent plusieurs minutes de
retard et se désactivent après soixante jours sans activité sur le dépôt.

---

## 3. L'API sur Render

1. Créer un compte sur [render.com](https://render.com) et le relier à GitHub.
2. **New** puis **Blueprint**, choisir le dépôt `hanabi`.
3. Render lit `render.yaml` et propose le service `hanabi-api`. Il demande les
   variables marquées `sync: false` :

   | Variable | Valeur |
   | --- | --- |
   | `DATABASE_URL` | la chaîne de connexion **directe** copiée à l'étape 2 |
   | `CORS_ORIGINS` | laisser vide pour l'instant (étape 5) |
   | `ADMIN_EMAIL` | l'adresse qui aura accès au back-office |
   | `ADMIN_PASSWORD` | au moins 10 caractères, ni courant ni répétitif, sans suite de touches |

   `SECRET_KEY` est générée par Render : rien à saisir, et elle ne transite
   jamais par le dépôt.

4. Lancer le déploiement, puis noter l'URL obtenue. Render y ajoute un suffixe
   aléatoire quand le nom du service est déjà pris ailleurs sur la plateforme :
   celle de ce déploiement est `https://hanabi-api-myk8.onrender.com`.

**Vérifier :** ouvrir `https://hanabi-api-myk8.onrender.com/health`. La réponse doit
être `{"status":"ok"}`.

Le premier démarrage est plus long : Alembic crée le schéma, puis le jeu de
démonstration est généré (`DEMO_USERS`, 100 000 comptes par défaut).

### Ce qu'implique l'offre gratuite de Render

- **Mise en veille après inactivité.** La première visite après une pause
  réveille le service et peut demander une minute. Les suivantes sont normales.
  Ouvre le lien une fois avant de le montrer à quelqu'un.
- **Disque non persistant.** Les données vivent dans PostgreSQL ; rien d'écrit
  sur le disque du conteneur ne survit à un redémarrage.

---

## 4. L'interface sur Cloudflare Pages

1. Créer un compte sur [dash.cloudflare.com](https://dash.cloudflare.com), puis
   ouvrir **Workers & Pages** et **Create application**, onglet **Pages**.
2. **Connect to Git**, autoriser GitHub, choisir le dépôt.
3. Renseigner la configuration de build :

   | Champ | Valeur |
   | --- | --- |
   | Framework preset | `React (Vite)` |
   | Build command | `npm run build` |
   | Build output directory | `dist` |
   | Root directory (advanced) | `hanabi-front` |

   Sans ce répertoire racine, Cloudflare construit la racine du dépôt et échoue.

4. Toujours dans la section avancée, ajouter les variables d'environnement :

   | Variable | Valeur |
   | --- | --- |
   | `VITE_API_URL` | `https://hanabi-api-myk8.onrender.com` |
   | `NODE_VERSION` | `20` |

   `VITE_API_URL` est lue **au moment du build** et inscrite dans le bundle : la
   modifier plus tard impose de relancer un déploiement. Sans elle, le code
   retombe sur `http://localhost:8000` et le site se charge sans aucun produit.

5. **Save and Deploy**, puis noter l'URL obtenue. Comme Render, Cloudflare
   ajoute un suffixe quand le nom du projet est déjà pris : celle de ce
   déploiement est `https://hanabi-6x9.pages.dev`. C'est cette URL exacte qui va
   dans `CORS_ORIGINS` à l'étape suivante.

Le repli SPA vient de `hanabi-front/public/_redirects`, recopié tel quel dans
`dist` par Vite. Sans lui, ouvrir directement `/produit/5` renverrait 404.

Le palier gratuit couvre 500 builds par mois, bande passante non facturée.

---

## 5. Relier les deux

Retourner sur Render, service `hanabi-api`, **Environment**, et renseigner
`CORS_ORIGINS` avec l'URL exacte de l'interface, protocole compris et **sans
barre oblique finale** :

```
CORS_ORIGINS=https://hanabi-6x9.pages.dev
```

Le service redémarre seul. Sans cette étape, le navigateur bloque tous les
appels à l'API et la boutique affiche « serveur injoignable ».

---

## 6. Consulter depuis un autre appareil

L'URL Cloudflare est publique : elle fonctionne depuis n'importe quel téléphone ou
ordinateur, sans réseau local ni configuration.

- Ouvrir `https://hanabi-6x9.pages.dev` sur le téléphone.
- Le thème clair ou sombre s'aligne automatiquement sur celui du système.
- Sur iOS et Android, le menu de partage propose d'ajouter le site à l'écran
  d'accueil : il s'ouvre alors comme une application.

> Si la boutique affiche « serveur injoignable » à la première ouverture, c'est
> l'API qui se réveille. Recharger après une minute.

---

## Vérifications après mise en ligne

- [ ] La grille affiche les douze produits.
- [ ] `/produit/5` ouvre directement la fiche (repli SPA).
- [ ] Le bouton Retour du navigateur parcourt les écrans.
- [ ] Le thème suit celui du système, et le bouton le change.
- [ ] La connexion fonctionne avec le compte d'essai affiché.
- [ ] `/admin` **refuse** ce compte d'essai et accepte `ADMIN_EMAIL`.
- [ ] Sur téléphone : le menu en tiroir s'ouvre depuis l'en-tête.
- [ ] L'onglet **Actions** de GitHub affiche les trois tâches de CI en vert.

---

## Bon à savoir avant de partager le lien

- **Aucun paiement n'est encaissé.** Le tunnel valide le format de la carte mais
  ne transmet aucune donnée bancaire. La mention sous le bouton de paiement le
  dit au visiteur et doit rester.
- **Les mentions légales comportent des champs entre crochets.** Aucune identité
  d'entreprise n'a été inventée. Un bandeau explique que le site est un projet
  personnel sans activité commerciale.
- **Le back-office est ouvert à qui détient `ADMIN_PASSWORD`.** Il donne accès
  aux adresses e-mail de tous les comptes créés sur le site.

---

## Mettre à jour le site

Les deux hébergeurs redéploient automatiquement à chaque envoi sur `main` :

```bash
git add -A && git commit -m "..." && git push
```

---

## Notes

- Render valide `render.yaml` avant de créer les services et signale toute clé
  obsolète.
