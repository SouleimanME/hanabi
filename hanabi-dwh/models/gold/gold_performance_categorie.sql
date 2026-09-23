-- Les trois familles du catalogue, agrégées depuis `gold_performance_produit` pour que les totaux concordent.
select
    categorie,
    count(*)::int                                   as references,
    count(*) filter (where actif)::int              as references_actives,
    sum(vues)::int                                  as vues,
    sum(commandes)::int                             as commandes,
    sum(unites)::int                                as unites,
    sum(ca_cents)::bigint                           as ca_cents,
    sum(marge_cents)::bigint                        as marge_cents,
    round(sum(marge_cents)::numeric / nullif(sum(ca_cents), 0), 4) as taux_marge,
    round(sum(commandes)::numeric / nullif(sum(vues), 0), 4)       as taux_conversion,
    round(sum(ca_cents)::numeric / nullif(sum(vues), 0))::bigint   as ca_par_vue_cents,
    sum(stock)::int                                 as stock,
    -- À comparer à la part du chiffre d'affaires
    round(sum(marge_cents)::numeric
          / nullif(sum(sum(marge_cents)) over (), 0), 4)           as part_marge,
    round(sum(ca_cents)::numeric
          / nullif(sum(sum(ca_cents)) over (), 0), 4)              as part_ca
from {{ ref('gold_performance_produit') }}
group by categorie
order by sum(ca_cents) desc
