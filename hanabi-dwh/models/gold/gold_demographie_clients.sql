-- Portrait d'achat par (ville, tranche d'âge, civilité), précalculé.
-- `valeur_par_client_cents` compte les non-acheteurs, pour comparer des segments de tailles différentes.
with achats as (

    select
        client_id,
        count(*)            as commandes,
        sum(total_cents)    as ca_cents
    from {{ ref('slv_commandes') }}
    where est_ca and client_id is not null
    group by client_id

)

select
    coalesce(nullif(client.ville, ''), '?')  as ville,
    client.tranche_age,
    client.civilite,
    count(*)::int                            as clients,
    count(achats.client_id)::int             as acheteurs,
    round(count(achats.client_id)::numeric / nullif(count(*), 0), 4) as taux_acheteurs,
    coalesce(sum(achats.commandes), 0)::int  as commandes,
    coalesce(sum(achats.ca_cents), 0)::bigint as ca_cents,
    round(coalesce(sum(achats.ca_cents), 0)::numeric
          / nullif(sum(achats.commandes), 0))::bigint as panier_moyen_cents,
    round(coalesce(sum(achats.ca_cents), 0)::numeric
          / nullif(count(*), 0))::bigint             as valeur_par_client_cents
from {{ ref('slv_clients') }} as client
left join achats on achats.client_id = client.client_id
-- Comptes administrateurs écartés
where not client.est_admin
group by 1, 2, 3
order by ca_cents desc, clients desc
