-- Calendrier quotidien : une ligne par jour, trouee par rien.
--
-- Le calendrier part de `generate_series` et non des faits. Un jour sans
-- commande doit exister et valoir zero, sinon la courbe se resserre et laisse
-- croire a une activite continue. C'est la meme regle que pour les series
-- mensuelles, appliquee au pas de temps inferieur.
--
-- TROIS DECISIONS METIER VIVENT ICI, ET NULLE PART AILLEURS.
--
-- 1. Le taux du jour est REPORTE. La BCE ne cote ni le week-end ni ses feries,
--    et une commande passee un dimanche est bien convertie a un taux : celui
--    de la derniere cotation connue, qui est exactement ce que fait une
--    banque. Un `NULL` obligerait chaque modele aval a refaire ce choix, et
--    deux d'entre eux finiraient par le faire differemment.
--
-- 2. Les feries francais et japonais sont DEUX COLONNES. La France est le pays
--    des clients : un ferie y deplace la demande. Le Japon est celui des
--    fournisseurs : un ferie y arrete l'expedition. Un drapeau unique
--    melangerait une cause de baisse des ventes avec une cause d'allongement
--    du delai de reassort.
--
-- 3. Seuls les feries NATIONAUX comptent. Un ferie regional ne ferme ni le
--    pays ni ses usines.
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

-- `last_value(...) ignore nulls` aurait dit cela en une ligne, mais
-- PostgreSQL ne connait pas cette clause : elle appartient a Oracle, BigQuery
-- et Snowflake. L'idiome portable consiste a compter les valeurs non nulles
-- depuis le debut : ce compteur ne bouge qu'a chaque nouvelle cotation, il
-- forme donc un identifiant de palier, et le maximum sur ce palier est la
-- derniere cotation connue.
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

    -- Jour ouvre au sens du pays concerne : ni week-end, ni ferie national.
    not (extract(isodow from j.jour) >= 6 or coalesce(j.ferie_fr, false)) as ouvre_fr,
    not (extract(isodow from j.jour) >= 6 or coalesce(j.ferie_jp, false)) as ouvre_jp,

    -- Derniere cotation connue. Le drapeau accompagne toujours la valeur :
    -- un taux reporte reste un taux, mais celui qui l'utilise doit pouvoir
    -- savoir qu'il n'a pas ete cote ce jour-la.
    max(j.taux) over (partition by j.palier) as taux_jpy,
    j.taux is null as taux_reporte

from paliers j
