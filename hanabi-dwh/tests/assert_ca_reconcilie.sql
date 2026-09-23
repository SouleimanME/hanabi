-- Le chiffre d'affaires concorde entre série mensuelle et silver ; la segmentation
-- en diffère exactement du montant des commandes invitées.
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
