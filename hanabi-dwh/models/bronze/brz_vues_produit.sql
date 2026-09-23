-- Consultations de fiche : ni IP ni empreinte ; `user_id` nul pour un visiteur anonyme.
select
    id,
    product_id,
    user_id,
    created_at
from {{ source('hanabi_oltp', 'product_views') }}
