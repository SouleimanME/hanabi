-- Codes promotionnels, y compris ceux qu'aucune commande ne mentionne.
select
    id,
    code,
    kind,
    percent,
    amount_cents,
    min_subtotal_cents,
    active,
    expires_at
from {{ source('hanabi_oltp', 'promos') }}
