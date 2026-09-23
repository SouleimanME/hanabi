-- Avis avec leurs périodes ; les non approuvés restent (gold les écarte).
select
    id                                      as avis_id,
    product_id                              as produit_id,
    user_id                                 as client_id,
    author_name                             as auteur,
    rating                                  as note,
    verified                                as achat_verifie,
    approved                                as approuve,
    created_at                              as depose_le,
    created_at::date                        as jour,
    to_char(created_at, 'YYYY-MM')          as mois
from {{ ref('brz_avis') }}
