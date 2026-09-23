-- Taux EUR vers JPY tels que publiés, jours non cotés compris (comblés en silver).
select
    jour,
    devise,
    taux,
    charge_le
from {{ source('hanabi_externe', 'taux_change') }}
