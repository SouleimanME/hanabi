# Politique de sécurité

Hanabi est une boutique **fictive**. Aucun paiement n'est encaissé, aucune donnée
bancaire ne quitte le navigateur, et les comptes clients sont générés.

Une faille reste bonne à signaler : le projet sert justement à montrer comment ces
sujets sont traités.

## Signaler une faille

Ouvre une **[security advisory privée](https://github.com/SouleimanME/hanabi/security/advisories/new)**
plutôt qu'une issue publique, qui exposerait le problème avant sa correction.

Décris le chemin d'exploitation et ce qu'il permet d'obtenir, pas seulement le
symptôme. Réponse sous quelques jours : c'est un projet personnel, sans astreinte.

## Comportements voulus

- **Les identifiants du back-office sont publics.** `hanabi@atelier.fr` est affiché
  dans la fenêtre de connexion pour que chacun puisse ouvrir le back-office. Le
  compte est bridé en lecture seule côté serveur (`DEMO_ADMIN_READONLY`) ;
  l'administrateur réel vient de variables d'environnement hors dépôt.
- **Le jeton d'authentification vit en `localStorage`.** Un script injecté peut le
  lire. Choix assumé pour garder une API sans session, compensé par une durée de vie
  courte.
- **Les compteurs anti-robots sont en mémoire du processus.** Ils ne survivent pas à
  un redémarrage et ne se partagent pas entre instances ; plusieurs répliques
  demanderaient Redis.

## Ce qui est défendu

| Sujet | Où |
| --- | --- |
| Preuve de travail, pot de miel, délai de saisie | `hanabi-back/app/antibot.py` |
| Politique de mot de passe (NIST SP 800-63B) | `hanabi-back/app/passwords.py` |
| Limitation par compte et par IP, en-têtes durcis | `hanabi-back/app/ratelimit.py` |
| Cloisonnement du back-office | `hanabi-back/app/deps.py` |
| Recalcul des montants côté serveur | `hanabi-back/app/pricing.py` |
| Jetons JWT, hachage bcrypt | `hanabi-back/app/security.py` |
| Console SQL en lecture seule | `hanabi-back/app/warehouse.py` |

Deux invariants à tester en priorité : **un prix envoyé par le client n'est jamais
cru**, et **le stock se décrémente par `UPDATE … WHERE stock >= qty`**, pour que deux
acheteurs simultanés du dernier article ne passent pas tous les deux.

## Secrets

Aucun secret n'est versionné. `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` et
`DATABASE_URL` viennent de l'environnement. En `ENV=prod`, l'API refuse de démarrer
sans `SECRET_KEY`.

Un secret retrouvé dans l'historique git est une vraie faille : signale-la.
