import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("hanabi.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Jamais de valeur en dur : voir `_resolve_secret`
    SECRET_KEY: str = ""

    # "prod" refuse de démarrer sans SECRET_KEY
    ENV: str = "dev"

    # Jeton en localStorage, donc lisible par un script injecté : durée courte
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "sqlite:///./atelier.db"
    # Hors production, le démarrage ne migre qu'une base locale (voir migrate.py).
    # À 1 pour migrer à dessein une base distante depuis un poste de travail.
    MIGRER_BASE_DISTANTE: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Compte administrateur ---
    # Créé ou promu au démarrage si les deux sont renseignés ; sinon aucun
    # administrateur n'est provisionné. Jamais dans le dépôt.
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # --- Back-office de démonstration ---
    # Compte administrateur aux identifiants publics, affichés à la connexion.
    PUBLIC_ADMIN_DEMO: bool = True
    # Interdit toute écriture sur /admin à ce compte. À 0, n'importe quel visiteur
    # peut modifier le site.
    DEMO_ADMIN_READONLY: bool = True

    # --- Jeu de données de démonstration ---
    # À zéro, seul le catalogue est créé. 100 000 comptes pèsent environ 143 Mo
    # (30 % du quota Neon gratuit) et gardent la segmentation RFM sous 1,2 s ;
    # vers 300 000, stockage et temps de calcul deviennent limites.
    DEMO_USERS: int = 100_000
    # Consultations de fiche par compte généré : fixe la taille de la plus grosse table
    DEMO_VIEWS_PER_USER: int = 7

    # --- Anti-robots (voir antibot.py) ---
    # Bits de zéros exigés sur la preuve de travail ; chaque bit double le coût.
    # 16 bits : environ 0,5 s sur un ordinateur, quelques secondes sur un
    # téléphone modeste, calculées pendant la saisie. Freine le volume, sans
    # arrêter seul un attaquant équipé.
    POW_DIFFICULTY: int = 16
    POW_TTL_SECONDS: int = 300
    # Délai minimal entre l'affichage d'un formulaire et son envoi
    MIN_FORM_SECONDS: float = 1.5

    # --- Conditions générales de vente ---
    # Enregistrée sur chaque commande : à changer avec le texte des CGV.
    CGV_VERSION: str = "2026-08"

    # --- Recherche (voir recherche.py) ---
    # Recherche par le sens, si le modèle est téléchargé (python -m app.plongement).
    # Sans lui, ou à False, la recherche par le texte et le prix répond seule.
    RECHERCHE_SEMANTIQUE: bool = True

    # --- Journalisation (voir observability.py) ---
    # JSON activé d'office en production, sauf réglage explicite
    LOG_JSON: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Courriels (voir mailer.py) ---
    # `fichier` : message .eml complet dans `var/courriels/`, sans identifiants.
    # `smtp` : relais réel (Brevo, Resend, Gmail avec mot de passe d'application).
    # `memoire` : suite de tests.
    MAIL_BACKEND: str = "fichier"
    MAIL_FROM: str = "commandes@hanabi.example"
    MAIL_FROM_NAME: str = "Hanabi"

    # Racine publique de la boutique (pas de l'API), utilisée dans les liens des courriels
    PUBLIC_SITE_URL: str = "http://localhost:5173"

    SMTP_HOST: str = ""
    # 587 : STARTTLS ; 465 : TLS dès l'ouverture. Le mode se déduit du port.
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT: int = 10

    # --- File des courriels (voir outbox.py) ---
    # À zéro, la tâche de fond ne démarre pas (tests)
    OUTBOX_INTERVALLE_SECONDES: float = 5.0
    OUTBOX_LOT: int = 20
    # Cinq tentatives espacées couvrent environ une demi-heure de panne du relais
    OUTBOX_TENTATIVES_MAX: int = 5

    # --- Idempotence (voir idempotency.py) ---
    IDEMPOTENCE_RETENTION_HEURES: int = 24

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() in {"prod", "production"}


def _resolve_secret(cfg: Settings) -> Settings:
    """Clé de signature obligatoire en production ; aléatoire en mémoire sinon."""
    if cfg.SECRET_KEY:
        return cfg

    if cfg.is_prod:
        raise RuntimeError(
            "SECRET_KEY est absente alors que ENV=prod. "
            "Génère une clé robuste et passe-la en variable d'environnement, "
            "par exemple : python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    cfg.SECRET_KEY = secrets.token_urlsafe(64)
    log.warning(
        "SECRET_KEY absente : clé aléatoire générée pour cette exécution. "
        "Les jetons deviendront invalides au redémarrage. "
        "Définis SECRET_KEY dans .env pour une session persistante."
    )
    return cfg


def _defauts_selon_environnement(cfg: Settings) -> Settings:
    """Défauts qui dépendent de l'environnement, sauf valeur fournie explicitement."""
    fournis = cfg.model_fields_set
    if "LOG_JSON" not in fournis and cfg.is_prod:
        cfg.LOG_JSON = True
    return cfg


def _verifie_cors(cfg: Settings) -> Settings:
    """Refuse l'origine « * » en production.

    Avec `allow_credentials=True`, Starlette renvoie l'origine demandée au lieu
    de `*` : tout site pourrait lire les réponses avec les identifiants du visiteur.
    """
    if cfg.is_prod and "*" in cfg.cors_list:
        raise RuntimeError(
            "CORS_ORIGINS contient « * » alors que ENV=prod. "
            "Avec les identifiants autorisés, cela ouvre l'API à tous les sites. "
            "Renseigne l'origine exacte de la boutique, par exemple : "
            "CORS_ORIGINS=https://hanabi-6x9.pages.dev"
        )
    return cfg


settings = _verifie_cors(_defauts_selon_environnement(_resolve_secret(Settings())))
