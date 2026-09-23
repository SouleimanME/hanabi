-- En-têtes de commande, sans filtre de statut (silver décide du chiffre d'affaires).
-- Ni e-mail ni adresse de livraison : le client se désigne par `user_id`.
select
    id,
    number,
    user_id,
    status,
    subtotal_cents,
    discount_cents,
    shipping_cents,
    total_cents,
    promo_code,
    created_at
from {{ source('hanabi_oltp', 'orders') }}
