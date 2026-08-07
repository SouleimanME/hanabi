-- En-tetes de commande, tels qu'ecrits par l'application.
--
-- Aucun filtre sur le statut ici : bronze reproduit la source. Une commande
-- annulee est un fait, et la couche silver decidera qu'elle ne compte pas dans
-- le chiffre d'affaires. Filtrer des la premiere couche rendrait impossible de
-- mesurer le taux d'annulation, qui est justement une des questions posees.
select
    id,
    number,
    user_id,
    email,
    status,
    subtotal_cents,
    discount_cents,
    shipping_cents,
    total_cents,
    promo_code,
    created_at
from {{ source('hanabi_oltp', 'orders') }}
