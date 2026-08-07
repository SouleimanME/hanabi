# Politique de sécurité

Hanabi est une boutique **fictive**, sans activité commerciale. Aucun paiement
n'est encaissé, aucune donnée bancaire ne quitte le navigateur, et les comptes
clients sont générés par le jeu de données de démonstration.

Cela réduit l'enjeu d'une faille, mais ne la rend pas moins intéressante à
signaler : le projet existe précisément pour montrer comment ces sujets sont
traités.

## Signaler une faille

Ouvre une **[security advisory privée](https://github.com/SouleimanME/hanabi-boutique/security/advisories/new)**
plutôt qu'une issue publique - une issue expose le problème avant qu'il soit
corrigé, et c'est vrai même sur un projet de démonstration.

Décris le chemin d'exploitation, pas seulement le symptôme : ce qui est utile,
c'est ce qu'un attaquant obtient au bout.

Je réponds sous quelques jours. Ce dépôt est un projet personnel, sans astreinte.

## Ce qui n'en est pas une

Trois comportements ressemblent à des failles et sont documentés comme des
choix. Les signaler ne dérange pas, mais autant le dire d'avance :

- **Les identifiants du back-office sont publics.** `hanabi@atelier.fr` est
  affiché dans la fenêtre de connexion, à dessein : n'importe qui doit pouvoir
  ouvrir le back-office. Ce compte est bridé en lecture seule côté serveur par
  `DEMO_ADMIN_READONLY`, et le compte administrateur réel est provisionné
  séparément par des variables d'environnement qui n'apparaissent jamais dans le
  dépôt.
- **Le jeton d'authentification vit en `localStorage`.** Il est donc lisible par
  un script injecté. Le choix est assumé pour garder une API sans état de
  session ; la contrepartie est une durée de vie courte.
- **Les compteurs anti-robots sont en mémoire du processus.** Ils ne survivent
  pas à un redémarrage et ne sont pas partagés entre instances. Derrière
  plusieurs répliques, il faudrait les déplacer dans Redis. C'est une limite
  connue, écrite dans `AGENTS.md`.

## Ce qui est réellement défendu

Si tu cherches où creuser, c'est ici que le code prend position :

| Sujet | Où |
| --- | --- |
| Preuve de travail, pot de miel, délai de saisie | `hanabi-back/app/antibot.py` |
| Politique de mot de passe (NIST SP 800-63B) | `hanabi-back/app/passwords.py` |
| Limitation par compte et par IP, en-têtes durcis | `hanabi-back/app/ratelimit.py` |
| Cloisonnement du back-office | `hanabi-back/app/deps.py` |
| Recalcul des montants côté serveur | `hanabi-back/app/pricing.py` |
| Jetons JWT, hachage bcrypt | `hanabi-back/app/security.py` |

Deux invariants valent d'être testés en priorité, parce que les casser aurait
des conséquences réelles : **un prix envoyé par le client n'est jamais cru**, et
**le stock se décrémente par `UPDATE … WHERE stock >= qty`** - deux acheteurs
simultanés sur le dernier article ne doivent pas passer tous les deux.

## Secrets

Aucun secret n'est versionné. `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` et
`DATABASE_URL` viennent de l'environnement. En `ENV=prod`, l'absence de
`SECRET_KEY` **empêche le démarrage** plutôt que de laisser signer des jetons
avec une clé connue.

Si tu trouves un secret dans l'historique git, c'est une vraie faille : signale-la.
