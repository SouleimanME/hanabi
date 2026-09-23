-- Lignes de commande, sans le visuel `art`. `name` est le nom figé à la commande.
select
    id,
    order_id,
    product_id,
    name,
    unit_price_cents,
    unit_cost_cents,
    qty
from {{ source('hanabi_oltp', 'order_items') }}
