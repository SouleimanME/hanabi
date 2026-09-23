{{
    config(
        materialized='incremental',
        unique_key='jour',
        incremental_strategy='delete+insert',
    )
}}

-- Chiffre d'affaires quotidien, avec calendrier et change.
--
-- - Référence : moyenne des quatre journées précédentes de même nature (ouvré,
--   week-end, férié), pour qu'un jour férié ne passe pas pour un incident.
-- - Effet de change : coût au taux du jour comparé au coût à un taux fixe.
-- - Incrémental avec 30 jours de rattrapage (remboursements tardifs). Les modèles
--   RFM ne peuvent pas l'être : la récence change chaque jour pour chaque client.
-- - La référence se calcule sur un an de contexte avant la fenêtre, puis seule la
--   fenêtre est écrite. Calculée dans la fenêtre seule, elle perdait ses jours
--   précédents : le premier jour de chaque passage sortait sans référence, et
--   chaque jour finissait par être ce premier jour.

{% set fenetre_rattrapage_jours = 30 %}

-- Un an contient toujours quatre jours de chaque nature (la France compte onze fériés)
{% set contexte_reference_jours = 366 %}

-- Taux de référence fixe : seul l'écart compte, et il ne doit pas changer à la reconstruction
{% set taux_reference = 165.0 %}

with fenetre as (

    {% if is_incremental() %}
        -- `coalesce` : sur une table vide, la comparaison à null ne garderait rien
        select coalesce(
            (select max(jour) from {{ this }}) - interval '{{ fenetre_rattrapage_jours }} days',
            '1900-01-01'::date
        )::date as debut
    {% else %}
        select '1900-01-01'::date as debut
    {% endif %}

),

jours as (

    select
        jour,
        jour_semaine,
        week_end,
        ferie_fr,
        ferie_jp,
        feries_nom,
        ouvre_fr,
        taux_jpy,
        taux_reporte
    from {{ ref('slv_calendrier_quotidien') }}
    where jour <= current_date
      and jour >= (select debut from fenetre) - interval '{{ contexte_reference_jours }} days'

),

ventes as (

    select
        jour,
        count(*)                    as commandes,
        count(distinct client_id)   as acheteurs,
        sum(total_cents)            as ca_cents,
        sum(remise_cents)           as remise_cents
    from {{ ref('slv_commandes') }}
    where est_ca
      and jour in (select jour from jours)
    group by jour

),

couts as (

    -- Les lignes portent déjà leur jour et `est_ca`
    select
        jour,
        sum(cout_cents) as cout_cents
    from {{ ref('slv_lignes_commande') }}
    where est_ca
      and jour in (select jour from jours)
    group by jour

),

assemble as (

    select
        j.jour,
        j.jour_semaine,
        j.week_end,
        j.ferie_fr,
        j.ferie_jp,
        j.feries_nom,
        j.ouvre_fr,
        j.taux_jpy,
        j.taux_reporte,

        coalesce(v.commandes, 0)    as commandes,
        coalesce(v.acheteurs, 0)    as acheteurs,
        coalesce(v.ca_cents, 0)     as ca_cents,
        coalesce(v.remise_cents, 0) as remise_cents,
        coalesce(c.cout_cents, 0)   as cout_cents,

        -- Nature du jour, pour comparer ce qui est comparable
        case
            when j.ferie_fr then 'ferie'
            when j.week_end then 'week-end'
            else 'ouvre'
        end as nature_jour

    from jours j
    left join ventes v on v.jour = j.jour
    left join couts  c on c.jour = j.jour

),

calcule as (

    select
        jour,
        jour_semaine,
        nature_jour,
        week_end,
        ferie_fr,
        ferie_jp,
        feries_nom,
        ouvre_fr,

        commandes,
        acheteurs,
        ca_cents,
        remise_cents,
        cout_cents,
        ca_cents - cout_cents as marge_cents,

        taux_jpy,
        taux_reporte,

        -- Coût en yen au taux du jour, et marge à change constant : l'écart isole l'effet de change
        round(cout_cents * taux_jpy / 100.0)                     as cout_jpy,
        round(ca_cents - cout_cents * ({{ taux_reference }} / taux_jpy)) as marge_change_constant_cents,

        -- Moyenne des quatre occurrences précédentes de même nature (`rows`, pas `range`)
        avg(ca_cents) over (
            partition by nature_jour
            order by jour
            rows between 4 preceding and 1 preceding
        )::bigint as ca_reference_cents

    from assemble

)

-- Le contexte a servi à la référence ; seule la fenêtre est écrite
select *
from calcule
where jour >= (select debut from fenetre)
