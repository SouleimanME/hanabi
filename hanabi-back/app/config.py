import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("hanabi.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Vide par defaut, et JAMAIS une valeur en dur : une cle de signature
    # presente dans le depot est une cle publique. Quiconque lit le code peut
    # alors forger un jeton pour n'importe quel compte, administrateur compris.
    # Le comportement en l'absence de cle est decide dans `_resolve_secret`.
    SECRET_KEY: str = ""

    # "prod" refuse de demarrer sans SECRET_KEY explicite.
    ENV: str = "dev"

    # Une semaine etait trop long pour un jeton stocke en localStorage, donc
    # lisible par n'importe quel script injecte. Douze heures reduisent la
    # fenetre d'exploitation d'un jeton vole sans forcer a se reconnecter
    # plusieurs fois par jour.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "sqlite:///./atelier.db"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Compte administrateur ---
    #
    # Vides par defaut, et jamais renseignes dans le depot. Le jeu de donnees de
    # demonstration cree un compte client (demo@hanabi.fr) dont les identifiants
    # sont affiches dans l'interface : lui donner les droits d'administration
    # ouvrait le back-office a tout visiteur d'un site mis en ligne.
    #
    # Si ces deux variables sont renseignees, le compte correspondant est cree
    # au demarrage, ou promu s'il existe deja. Sinon, aucun administrateur n'est
    # provisionne et le back-office reste inaccessible.
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # --- Back-office vitrine ---
    #
    # Compte administrateur aux identifiants publics, affiches dans la fenetre
    # de connexion sous le compte client de demonstration. Il existe pour qu'un
    # recruteur puisse ouvrir le back-office sans qu'on lui transmette quoi que
    # ce soit.
    #
    # Consequence directe : n'importe quel visiteur y accede. C'est pourquoi il
    # est bride en lecture seule par defaut (voir `DEMO_ADMIN_READONLY`), sans
    # quoi le premier passant pourrait vider le catalogue, supprimer les codes
    # promo ou exporter la liste des clients.
    PUBLIC_ADMIN_DEMO: bool = True

    # Interdit au compte vitrine toute ecriture sur /admin : il consulte, il ne
    # modifie pas. Passer a 0 lui rend les droits complets - a ne faire que si
    # l'on accepte que le contenu du site soit modifiable par quiconque lit la
    # page de connexion.
    DEMO_ADMIN_READONLY: bool = True

    # --- Jeu de donnees analytique ---
    #
    # Le tableau de bord ne demontre rien sur une base vide : un histogramme a
    # trois barres et un taux de conversion calcule sur deux commandes ne
    # ressemblent pas a ce que produit une vraie boutique. On genere donc une
    # population fictive, dont le volume est regle ici.
    #
    # A zero, rien n'est genere et la base reste limitee au catalogue.
    #
    # 100 000 est un plafond mesure, pas choisi au hasard. Sur le palier gratuit
    # de l'hebergeur de base de donnees, ce volume represente environ 143 Mo,
    # soit 30 % du quota, et laisse donc de la place pour de vrais clients et
    # des photos produit. Cote calcul, l'agregation des 700 000 consultations
    # sur trente jours coute 3 ms grace aux index, et l'analyse la plus lourde -
    # la segmentation RFM, qui remonte tous les acheteurs en memoire - reste
    # sous les 1,2 s.
    #
    # Deux murs apparaissent au-dela : vers 300 000 comptes le stockage depasse
    # 85 % du quota, et la segmentation approche les 3,5 s, seuil ou une page
    # cesse d'etre agreable.
    DEMO_USERS: int = 100_000
    # Nombre moyen de consultations de fiche par compte genere. Determine le
    # volume de la table la plus grosse du schema, donc la duree du demarrage.
    DEMO_VIEWS_PER_USER: int = 7

    # --- Anti-robots (voir antibot.py) ---
    # Bits de zeros exiges sur l'empreinte de la preuve de travail. Chaque bit
    # double le cout. 16 bits demandent environ une demi-seconde a un ordinateur
    # de bureau et quelques secondes a un telephone d'entree de gamme ; comme le
    # calcul est lance des l'ouverture du formulaire, il se termine pendant la
    # saisie et ne se voit pas.
    #
    # A ne pas surestimer : un attaquant determine calcule ces empreintes en
    # code natif, bien plus vite qu'un navigateur. La preuve de travail freine le
    # spam automatise et le rend couteux en volume ; ce sont les autres barrieres
    # (limitation par IP et par compte, pot de miel, delai minimal) qui
    # completent la defense.
    POW_DIFFICULTY: int = 16
    # Duree de validite d'un defi.
    POW_TTL_SECONDS: int = 300
    # Delai minimal entre l'affichage d'un formulaire et son envoi. Un humain
    # met plusieurs secondes a saisir ; un robot repond instantanement.
    MIN_FORM_SECONDS: float = 1.5

    # --- Conditions generales de vente ---
    #
    # La version acceptee est enregistree sur chaque commande. A CHANGER des que
    # le texte des conditions change : sans cela, on saurait qu'une personne a
    # coche une case, mais pas ce qu'elle a accepte - et c'est precisement ce
    # qu'il faut pouvoir prouver.
    CGV_VERSION: str = "2026-08"

    # --- Journalisation (voir observability.py) ---
    #
    # Le JSON s'active de lui-meme en production : les hebergeurs l'indexent et
    # le rendent interrogeable, alors que la meme ligne sur un terminal de
    # developpement est illisible. Le reglage reste forcable dans les deux sens.
    LOG_JSON: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Courriels (voir mailer.py) ---
    #
    # `fichier` par defaut, et c'est un vrai mode de fonctionnement, pas un
    # bouchon : le message complet est ecrit dans `var/courriels/` au format
    # .eml, ouvrable d'un double-clic. Le depot reste ainsi clonable sans
    # identifiants, ce qu'un SMTP par defaut interdirait.
    #
    # `smtp` bascule sur un vrai relais. Gratuits et suffisants pour ce projet :
    # Brevo (300/jour a vie), Resend (3 000/mois), Gmail avec un mot de passe
    # d'application (500/jour). Tous parlent le SMTP standard.
    #
    # `memoire` est reserve a la suite de tests.
    MAIL_BACKEND: str = "fichier"
    MAIL_FROM: str = "commandes@hanabi.example"
    MAIL_FROM_NAME: str = "Hanabi"

    # Racine publique de la BOUTIQUE, pas de l'API : c'est elle qui figure dans
    # les liens de confirmation et de reinitialisation. Une valeur fausse produit
    # des courriels dont les liens ne menent nulle part - panne silencieuse, que
    # rien ne signale cote serveur puisque l'envoi, lui, a reussi.
    PUBLIC_SITE_URL: str = "http://localhost:5173"

    SMTP_HOST: str = ""
    # 587 (STARTTLS) est le port courant ; 465 ouvre directement en TLS. Le code
    # deduit le mode du port, parce que les confondre produit une attente muette
    # jusqu'au delai d'expiration plutot qu'une erreur lisible.
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT: int = 10

    # --- File d'attente des courriels (voir outbox.py) ---
    #
    # A zero, la tache de fond ne demarre pas : c'est ce que fait la suite de
    # tests, qui declenche la remise elle-meme pour rester deterministe.
    OUTBOX_INTERVALLE_SECONDES: float = 5.0
    OUTBOX_LOT: int = 20
    # Au-dela, le message est abandonne plutot que reessaye indefiniment. Cinq
    # tentatives espacees exponentiellement couvrent environ une demi-heure
    # d'indisponibilite du relais, ce qui absorbe l'immense majorite des pannes
    # passageres sans encombrer la file de messages voues a l'echec.
    OUTBOX_TENTATIVES_MAX: int = 5

    # --- Idempotence (voir idempotency.py) ---
    #
    # Duree au-dela de laquelle une cle est oubliee. Assez longue pour couvrir
    # tous les reessais plausibles d'un client, assez courte pour que la table
    # ne croisse pas indefiniment.
    IDEMPOTENCE_RETENTION_HEURES: int = 24

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() in {"prod", "production"}


def _resolve_secret(cfg: Settings) -> Settings:
    """Garantit une cle de signature sure, ou empeche le demarrage.

    En production, l'absence de cle est une erreur de deploiement : mieux vaut
    un service qui refuse de demarrer qu'un service qui accepte des jetons
    forges. En developpement, on tire une cle aleatoire en memoire - les jetons
    ne survivent pas a un redemarrage, ce qui est un inconvenient acceptable et
    bien preferable a une cle partagee par tous les clones du projet.
    """
    if cfg.SECRET_KEY:
        return cfg

    if cfg.is_prod:
        raise RuntimeError(
            "SECRET_KEY est absente alors que ENV=prod. "
            "Genere une cle robuste et passe-la en variable d'environnement, "
            "par exemple : python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    cfg.SECRET_KEY = secrets.token_urlsafe(64)
    log.warning(
        "SECRET_KEY absente : cle aleatoire generee pour cette execution. "
        "Les jetons deviendront invalides au redemarrage. "
        "Definis SECRET_KEY dans .env pour une session persistante."
    )
    return cfg


def _defauts_selon_environnement(cfg: Settings) -> Settings:
    """Aligne sur l'environnement les reglages dont le bon defaut en depend.

    Seulement si l'on n'a rien dit : une valeur posee explicitement dans `.env`
    l'emporte toujours. On regarde donc les champs REELLEMENT fournis plutot que
    la valeur courante, qu'on ne saurait pas distinguer du defaut.
    """
    fournis = cfg.model_fields_set
    if "LOG_JSON" not in fournis and cfg.is_prod:
        cfg.LOG_JSON = True
    return cfg


settings = _defauts_selon_environnement(_resolve_secret(Settings()))
