-- Calendrier quotidien continu (`generate_series`) : un jour sans commande vaut zéro.
--
-- - Taux reporté sur les jours non cotés, avec un drapeau.
-- - Fériés français (demande) et japonais (réassort) en deux colonnes.
-- - Seuls les fériés nationaux comptent.
with jours as (
    select generate_series(
        (select min(jour) from {{ ref('brz_taux_change') }}),
        greatest(current_date, (select max(jour) from {{ ref('brz_taux_change') }})),
        interval '1 day'
    )::date as jour
),

feries as (
    select
        jour,
        bool_or(pays = 'FR') as ferie_fr,
        bool_or(pays = 'JP') as ferie_jp,
        string_agg(nom_local, ', ' order by pays) as feries_nom
    from {{ ref('brz_jours_feries') }}
    where national
    group by jour
),

-- PostgreSQL n'a pas `ignore nulls` : le compteur de valeurs non nulles forme un
-- palier, dont le maximum est la dernière cotation connue.
paliers as (
    select
        j.jour,
        t.taux,
        count(t.taux) over (order by j.jour rows unbounded preceding) as palier,
        f.ferie_fr,
        f.ferie_jp,
        f.feries_nom
    from jours j
    left join {{ ref('brz_taux_change') }} t
        on t.jour = j.jour and t.devise = 'JPY'
    left join feries f
        on f.jour = j.jour
)

select
    j.jour,
    extract(isodow from j.jour)::int as jour_semaine,
    extract(isodow from j.jour) >= 6 as week_end,

    coalesce(j.ferie_fr, false) as ferie_fr,
    coalesce(j.ferie_jp, false) as ferie_jp,
    j.feries_nom,

    -- Ni week-end, ni férié national
    not (extract(isodow from j.jour) >= 6 or coalesce(j.ferie_fr, false)) as ouvre_fr,
    not (extract(isodow from j.jour) >= 6 or coalesce(j.ferie_jp, false)) as ouvre_jp,

    -- Dernière cotation connue, et drapeau si elle est reportée
    max(j.taux) over (partition by j.palier) as taux_jpy,
    j.taux is null as taux_reporte

from paliers j
