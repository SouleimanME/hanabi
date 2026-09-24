-- Lignes de commande, sans le visuel `art`. `name` et `category` sont figés à la commande.
select
    id,
    order_id,
    product_id,
    name,
    category,
    unit_price_cents,
    unit_cost_cents,
    qty
from {{ source('hanabi_oltp', 'order_items') }}
