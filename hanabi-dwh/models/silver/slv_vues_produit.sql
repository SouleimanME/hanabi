-- Consultations avec leurs périodes. Vue : les modèles gold l'agrègent aussitôt.
select
    id                                      as vue_id,
    product_id                              as produit_id,
    user_id                                 as client_id,
    -- Visiteur non connecté
    user_id is not null                     as identifie,
    created_at                              as vue_le,
    created_at::date                        as jour,
    date_trunc('month', created_at)::date   as mois_date,
    to_char(created_at, 'YYYY-MM')          as mois
from {{ ref('brz_vues_produit') }}
