-- Avis clients, tels qu'écrits par l'application, texte compris.
select
    id,
    product_id,
    user_id,
    author_name,
    rating,
    text,
    verified,
    approved,
    created_at
from {{ source('hanabi_oltp', 'reviews') }}
