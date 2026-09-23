-- Mois continus du premier événement au mois courant : un mois vide sort à zéro.
with bornes as (

    -- Mois courant en repli : une base vide donne une ligne
    select
        least(
            coalesce((select min(mois_date) from {{ ref('slv_commandes') }}), date_trunc('month', current_date)::date),
            coalesce((select min(mois_inscription_date) from {{ ref('slv_clients') }}), date_trunc('month', current_date)::date),
            coalesce((select min(mois_date) from {{ ref('slv_vues_produit') }}), date_trunc('month', current_date)::date)
        ) as premier_mois,
        date_trunc('month', current_date)::date as dernier_mois

),

serie as (

    select generate_series(premier_mois, dernier_mois, interval '1 month')::date as mois_date
    from bornes

)

select
    mois_date,
    to_char(mois_date, 'YYYY-MM')   as mois,
    extract(year from mois_date)::int  as annee,
    extract(month from mois_date)::int as numero_mois,
    -- Rang du mois, pour les régressions
    row_number() over (order by mois_date)::int as rang
from serie
