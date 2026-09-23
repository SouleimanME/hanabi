-- Comptes clients, tels qu'écrits par l'application.
-- Colonnes énumérées : ni `password_hash`, ni nom, e-mail, téléphone ou adresse
-- n'entrent dans l'entrepôt. Les analyses n'en ont pas besoin, et la console
-- SQL du back-office les exposerait (RGPD, minimisation).
select
    id,
    civility,
    birthdate,
    city,
    is_admin,
    created_at
from {{ source('hanabi_oltp', 'users') }}
