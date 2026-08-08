-- Jours feries francais et japonais, tels que la source les publie.
--
-- Les deux pays cohabitent dans la meme table parce qu'ils partagent le meme
-- schema, mais ils ne servent pas la meme question : la France porte la
-- demande, le Japon porte l'approvisionnement. C'est silver qui les separe en
-- deux colonnes, la ou la distinction devient une regle metier.
select
    jour,
    pays,
    nom,
    nom_local,
    national,
    charge_le
from {{ source('hanabi_externe', 'jours_feries') }}
