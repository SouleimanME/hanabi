-- Taux de reference EUR vers JPY, tels que la BCE les publie.
--
-- Aucune transformation, pas meme le comblement des jours non cotes : bronze
-- recopie ce que la source a dit, y compris ses trous. Les combler ici
-- reviendrait a inventer une cotation un dimanche.
select
    jour,
    devise,
    taux,
    charge_le
from {{ source('hanabi_externe', 'taux_change') }}
