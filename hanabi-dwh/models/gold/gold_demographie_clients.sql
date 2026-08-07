-- Portrait d'achat par croisement demographique.
--
-- Une ligne par (ville, tranche d'age, civilite) : c'est la forme qui repond a
-- la question que pose naturellement un histogramme de repartition. Un
-- graphique dit combien ils sont ; il ne dit pas ce qu'ils valent, et c'est
-- pourtant la seule chose qui justifie de leur parler.
--
-- Le croisement est calcule une fois pour toutes plutot qu'a la demande, comme
-- le fait la route d'exploration du back-office : les combinaisons sont peu
-- nombreuses - quelques centaines de lignes - et un filtre sur une table
-- precalculee coute infiniment moins qu'une agregation sur la table des
-- commandes a chaque clic.
--
-- `valeur_par_client_cents` compte les non-acheteurs au denominateur, a dessein.
-- C'est ce qui permet de comparer deux segments de taille differente, la ou le
-- chiffre d'affaires brut favorise toujours le plus nombreux.
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
-- Les comptes administrateurs sont ecartes : ce sont des comptes de service,
-- et les compter parmi la clientele fausserait les taux sur les segments peu
-- nombreux.
where not client.est_admin
group by 1, 2, 3
order by ca_cents desc, clients desc
