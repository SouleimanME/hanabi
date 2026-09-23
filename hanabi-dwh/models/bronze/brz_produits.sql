-- Catalogue, sans les visuels `art` et `images`.
select
    id,
    code,
    name,
    category,
    blurb,
    price_cents,
    cost_cents,
    stock,
    is_new,
    active,
    featured
from {{ source('hanabi_oltp', 'products') }}
