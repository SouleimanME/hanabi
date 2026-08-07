-- Le chiffre d'affaires doit etre le meme partout ou il apparait.
--
-- Trois tables le calculent par trois chemins differents : la serie mensuelle
-- part du calendrier, la segmentation part des clients, et la couche silver
-- part des commandes. Un tableau de bord ou ces trois nombres different perd
-- toute credibilite, et la divergence ne se voit pas a l'oeil - il faut la
-- chercher.
--
-- La segmentation est comparee a part : elle exclut les commandes invitees,
-- qui ne sont rattachees a aucun compte. L'ecart attendu est donc exactement
-- le montant de ces commandes-la, et non zero. Le confondre avec une erreur de
-- calcul serait le contresens le plus facile a commettre ici.
with mensuel as (

    select coalesce(sum(ca_cents), 0) as ca_cents
    from {{ ref('gold_kpi_mensuel') }}

),

commandes as (

    select
        coalesce(sum(total_cents), 0)                                        as ca_cents,
        coalesce(sum(total_cents) filter (where client_id is not null), 0)   as ca_rattache
    from {{ ref('slv_commandes') }}
    where est_ca

),

segmentation as (

    select coalesce(sum(montant_cents), 0) as ca_cents
    from {{ ref('gold_clients_rfm') }}

)

select
    mensuel.ca_cents        as ca_mensuel,
    commandes.ca_cents      as ca_commandes,
    segmentation.ca_cents   as ca_segmentation,
    commandes.ca_rattache   as ca_rattache_attendu
from mensuel
cross join commandes
cross join segmentation
where mensuel.ca_cents <> commandes.ca_cents
   or segmentation.ca_cents <> commandes.ca_rattache
