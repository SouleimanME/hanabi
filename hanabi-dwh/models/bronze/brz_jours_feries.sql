-- Jours fériés français et japonais, tels que la source les publie.
select
    jour,
    pays,
    nom,
    nom_local,
    national,
    charge_le
from {{ source('hanabi_externe', 'jours_feries') }}
