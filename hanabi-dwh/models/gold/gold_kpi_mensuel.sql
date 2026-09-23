{{
    config(
        materialized='incremental',
        unique_key='mois_date',
        incremental_strategy='delete+insert',
    )
}}

-- Série mensuelle des indicateurs.
--
-- Incrémental avec deux mois de rattrapage (remboursements tardifs). Part du
-- calendrier pour qu'un mois vide sorte à zéro. Chaque source est agrégée avant
-- le rapprochement, pour ne pas multiplier les lignes.
with ventes as (

    select
        mois_date,
        count(*)                        as commandes,
        sum(total_cents)                as ca_cents,
        sum(remise_cents)               as remise_cents,
        count(distinct client_id)       as acheteurs
    from {{ ref('slv_commandes') }}
    where est_ca
    group by mois_date

),

lignes as (

    select
        mois_date,
        sum(marge_cents)                as marge_cents,
        sum(quantite)                   as articles
    from {{ ref('slv_lignes_commande') }}
    where est_ca
    group by mois_date

),

audience as (

    select mois_date, count(*) as vues
    from {{ ref('slv_vues_produit') }}
    group by mois_date

),

inscriptions as (

    select mois_inscription_date as mois_date, count(*) as inscriptions
    from {{ ref('slv_clients') }}
    group by mois_inscription_date

)

select
    calendrier.mois,
    calendrier.mois_date,
    calendrier.rang,

    coalesce(ventes.ca_cents, 0)::bigint        as ca_cents,
    coalesce(lignes.marge_cents, 0)::bigint     as marge_cents,
    coalesce(ventes.remise_cents, 0)::bigint    as remise_cents,
    coalesce(ventes.commandes, 0)::int          as commandes,
    coalesce(lignes.articles, 0)::int           as articles,
    coalesce(ventes.acheteurs, 0)::int          as acheteurs,
    coalesce(inscriptions.inscriptions, 0)::int as inscriptions,
    coalesce(audience.vues, 0)::int             as vues,

    -- NULL sans commande : un panier moyen à 0 € serait trompeur
    round(coalesce(ventes.ca_cents, 0)::numeric
          / nullif(ventes.commandes, 0))::bigint            as panier_moyen_cents,
    round(coalesce(lignes.marge_cents, 0)::numeric
          / nullif(ventes.ca_cents, 0), 4)                  as taux_marge,
    round(coalesce(ventes.commandes, 0)::numeric
          / nullif(audience.vues, 0), 4)                    as taux_conversion,
    round(coalesce(ventes.ca_cents, 0)::numeric
          / nullif(audience.vues, 0))::bigint               as ca_par_vue_cents

from {{ ref('slv_calendrier_mensuel') }} as calendrier
left join ventes        on ventes.mois_date = calendrier.mois_date
left join lignes        on lignes.mois_date = calendrier.mois_date
left join audience      on audience.mois_date = calendrier.mois_date
left join inscriptions  on inscriptions.mois_date = calendrier.mois_date
{% if is_incremental() %}
    -- `coalesce` : sans lui, la première exécution incrémentale ne construirait rien
    where calendrier.mois_date >= coalesce(
        (select max(mois_date) from {{ this }}) - interval '2 months',
        '1900-01-01'::date
    )
{% endif %}
order by calendrier.mois_date
