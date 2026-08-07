-- Lignes de commande, telles qu'ecrites par l'application.
--
-- `art` est ecarte pour la meme raison que dans le catalogue : la ligne en
-- conserve une copie du visuel, qui peut peser autant que tout le reste de la
-- table reunie.
--
-- `name`, en revanche, est conserve bien qu'il double `products.name` : c'est
-- le nom fige au moment de la commande. Le rapprocher du nom courant du
-- catalogue permet de reperer les fiches renommees depuis.
select
    id,
    order_id,
    product_id,
    name,
    unit_price_cents,
    unit_cost_cents,
    qty
from {{ source('hanabi_oltp', 'order_items') }}
