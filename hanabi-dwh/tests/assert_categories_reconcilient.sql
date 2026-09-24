-- Les ventes par famille totalisent celles par produit. Les deux tables lisent les
-- mêmes lignes de commande, l'une par catégorie figée, l'autre par produit : une
-- jointure qui perd ou double une famille se voit ici.
with familles as (

    select coalesce(sum(ca_cents), 0) as ca_cents, coalesce(sum(unites), 0) as unites
    from {{ ref('gold_performance_categorie') }}

),

produits as (

    select coalesce(sum(ca_cents), 0) as ca_cents, coalesce(sum(unites), 0) as unites
    from {{ ref('gold_performance_produit') }}

)

select
    familles.ca_cents   as ca_familles,
    produits.ca_cents   as ca_produits,
    familles.unites     as unites_familles,
    produits.unites     as unites_produits
from familles
cross join produits
where familles.ca_cents <> produits.ca_cents
   or familles.unites <> produits.unites
