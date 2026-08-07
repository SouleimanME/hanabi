# Mise en ligne

Objectif : une URL publique, gratuite, consultable depuis n'importe quel
appareil. Compter une trentaine de minutes la première fois.

Hanabi se compose de deux projets à héberger séparément :

| Projet | Nature | Hébergeur | Fichier de config |
| --- | --- | --- | --- |
| `hanabi-front` | build statique (Vite) | Cloudflare Pages | `hanabi-front/public/_redirects` |
| `hanabi-back` | service Python (FastAPI) | Render | `render.yaml` |

Ce découpage tient à la nature des deux : un build statique se diffuse depuis un
réseau de cache, sans mise en veille ni temps de démarrage, alors que l'API a
besoin d'un processus vivant.

Tout ce qui peut l'être est déclaré dans ces deux fichiers. Restent quelques
valeurs à saisir à la main, parce qu'elles ne peuvent pas figurer dans un dépôt
ou ne sont connues qu'après le premier déploiement.

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
envoi : elle joue la suite de tests de l'API, le lint et le build de
l'interface, puis l'analyse du projet dbt. L'onglet **Actions** du dépôt doit
afficher trois coches vertes.

---

## 2. La base sur Neon

À faire avant Render : la chaîne de connexion obtenue ici est demandée à l'étape
suivante.

1. Créer un compte sur [neon.com](https://neon.com).
2. **Create project**. Choisir une région proche de celle du service Render
   (`aws-eu-central-1` pour Francfort) : chaque requête traverse le réseau, et
   deux continents ajoutent une centaine de millisecondes à chacune.
3. Dans **Connection Details**, copier la chaîne de connexion **directe** —
   celle proposée par défaut, dont le nom d'hôte ne comporte pas `-pooler`.

   Le gestionnaire de connexions de Neon travaille en mode transaction et ne
   conserve pas l'état de session. Or l'API fixe le fuseau de sa session à UTC
   (`options: -c timezone=utc` dans `database.py`), sans quoi une commande
   passée en fin de mois basculerait dans le mois suivant au moment du
   regroupement, et les séries mensuelles du tableau de bord seraient fausses.
   Ce réglage serait perdu derrière le pooler. L'API gérant déjà son propre
   pool SQLAlchemy, celui de Neon n'apporterait de toute façon rien.

La chaîne ressemble à ceci, le mot de passe en clair au milieu :

```
postgresql://neondb_owner:MOT_DE_PASSE@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

Elle ne doit apparaître ni dans le dépôt, ni dans une capture, ni dans un
message. Elle se colle directement dans le tableau de bord Render, et nulle part
ailleurs.

**Rien à créer côté schéma.** Les tables et les index sont posés par Alembic au
premier démarrage de l'API, puis le jeu de données de démonstration est généré
dans la foulée.

### Ce qu'implique l'offre gratuite de Neon

- 0,5 Go de stockage et 100 CU-heures de calcul par mois. Le jeu de données
  complet, dix mille comptes compris, pèse moins de 100 Mo : la marge est large.
- **Mise en veille au bout de cinq minutes** sans requête, non désactivable. Le
  réveil prend quelques centaines de millisecondes, et le pool est configuré
  pour le supporter (`pool_pre_ping`).
- Pas de date d'expiration : le projet reste en place tant qu'il est utilisé.

---

## 3. L'API sur Render

1. Créer un compte sur [render.com](https://render.com) et le relier à GitHub.
2. **New** puis **Blueprint**, choisir le dépôt `hanabi`.
3. Render lit `render.yaml` et propose le service `hanabi-api`. Il demande les
   variables marquées `sync: false` :

   | Variable | Valeur |
   | --- | --- |
   | `DATABASE_URL` | la chaîne *pooled* copiée à l'étape 2 |
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

Le tout premier démarrage est plus long que les suivants : Alembic crée le
schéma, puis dix mille comptes et leur historique sont générés. Compter une
poignée de secondes supplémentaires, une seule fois.

### Ce qu'implique l'offre gratuite de Render

- **Mise en veille après inactivité.** La première visite après une pause
  réveille le service et peut demander une minute. Les suivantes sont normales.
  Ouvre le lien une fois avant de le montrer à quelqu'un.
- **Disque non persistant.** Sans conséquence désormais : les données vivent
  dans PostgreSQL, pas dans le conteneur. Rien ne doit être écrit sur le disque
  avec l'espoir de le retrouver au redémarrage.

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

   Le répertoire racine est le piège de ce dépôt : il contient deux projets, et
   sans cette valeur Cloudflare construit la racine et échoue.

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
   déploiement est `https://hanabi-6x9.pages.dev`. C'est cette URL exacte, et
   pas celle qu'on avait prévue, qui doit être reportée dans `CORS_ORIGINS` à
   l'étape suivante.

Le repli SPA vient de `hanabi-front/public/_redirects`, recopié tel quel dans
`dist` par Vite. Sans lui, ouvrir directement `/produit/5` renverrait 404.

Le palier gratuit couvre 500 builds par mois et ne facture pas la bande
passante, ce qui laisse de la marge pour un projet de portfolio.

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
- [ ] `/produit/5` ouvre directement la fiche - c'est la règle de repli SPA.
- [ ] Le bouton Retour du navigateur parcourt les écrans.
- [ ] Le thème suit celui du système, et le bouton le change.
- [ ] La connexion fonctionne avec le compte d'essai affiché.
- [ ] `/admin` **refuse** ce compte d'essai et accepte `ADMIN_EMAIL`.
- [ ] Sur téléphone : la barre du bas remplace les actions de l'en-tête.
- [ ] L'onglet **Actions** de GitHub affiche deux coches vertes.

---

## Bon à savoir avant de partager le lien

- **Aucun paiement n'est encaissé.** Le tunnel valide le format de la carte mais
  ne transmet aucune donnée bancaire, et la mention sous le bouton de paiement
  le dit au visiteur. Elle doit rester : sans elle, quelqu'un pourrait saisir une
  vraie carte sur un site qui n'a pas de prestataire de paiement.
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

- Les schémas de configuration des hébergeurs évoluent. Render valide
  `render.yaml` avant de créer les services et signale toute clé obsolète ;
  Cloudflare Pages reconstruit de même a chaque poussee sur `main`.
- Les deux fichiers sont commentés : chaque réglage explique ce qu'il fait et ce
  qui casse en son absence.
