-- Les familles du catalogue. Les ventes suivent la catégorie figée sur chaque ligne de
-- commande ; références, audience et stock suivent la catégorie actuelle des produits.
-- Un objet reclassé emporte son audience et son stock, pas son chiffre d'affaires passé.
with catalogue as (

    select
        categorie,
        count(*)::int                       as references,
        count(*) filter (where actif)::int  as references_actives,
        sum(vues)::int                      as vues,
        sum(stock)::int                     as stock
    from {{ ref('gold_performance_produit') }}
    group by categorie

),

ventes as (

    select
        categorie,
        -- Deux articles de la même famille font une seule commande
        count(distinct commande_id)::int    as commandes,
        sum(quantite)::int                  as unites,
        sum(ca_cents)::bigint               as ca_cents,
        sum(marge_cents)::bigint            as marge_cents
    from {{ ref('slv_lignes_commande') }}
    where est_ca
    group by categorie

),

-- Une famille sans référence restante peut garder des ventes, et l'inverse
assemble as (

    select
        coalesce(catalogue.categorie, ventes.categorie) as categorie,
        coalesce(catalogue.references, 0)               as references,
        coalesce(catalogue.references_actives, 0)       as references_actives,
        coalesce(catalogue.vues, 0)                     as vues,
        coalesce(ventes.commandes, 0)                   as commandes,
        coalesce(ventes.unites, 0)                      as unites,
        coalesce(ventes.ca_cents, 0)::bigint            as ca_cents,
        coalesce(ventes.marge_cents, 0)::bigint         as marge_cents,
        coalesce(catalogue.stock, 0)                    as stock
    from catalogue
    full outer join ventes on ventes.categorie = catalogue.categorie

)

select
    categorie,
    -- Mot réservé de PostgreSQL : nommé par sa table
    assemble.references,
    references_actives,
    vues,
    commandes,
    unites,
    ca_cents,
    marge_cents,
    round(marge_cents::numeric / nullif(ca_cents, 0), 4)            as taux_marge,
    round(commandes::numeric / nullif(vues, 0), 4)                  as taux_conversion,
    round(ca_cents::numeric / nullif(vues, 0))::bigint              as ca_par_vue_cents,
    stock,
    -- À comparer à la part du chiffre d'affaires
    round(marge_cents::numeric / nullif(sum(marge_cents) over (), 0), 4) as part_marge,
    round(ca_cents::numeric / nullif(sum(ca_cents) over (), 0), 4)       as part_ca
from assemble
order by ca_cents desc
