-- Clients conformés : démographie et cohorte d'inscription.
-- Âge d'après l'année de naissance, comme `analytics.py`. Administrateurs conservés.
with source as (

    select * from {{ ref('brz_clients') }}

),

calcule as (

    select
        id                                          as client_id,
        city                                        as ville,
        is_admin                                    as est_admin,
        created_at                                  as inscrit_le,
        date_trunc('month', created_at)::date       as mois_inscription_date,
        to_char(created_at, 'YYYY-MM')              as mois_inscription,

        -- « ? » pour une civilité absente
        coalesce(nullif(civility, ''), '?')         as civilite,

        -- Quatre premiers caractères pris seulement s'ils sont des chiffres
        case
            when birthdate ~ '^\d{4}' then substring(birthdate from 1 for 4)::int
        end                                         as annee_naissance
    from source

)

select
    client_id,
    ville,
    est_admin,
    inscrit_le,
    mois_inscription,
    mois_inscription_date,
    civilite,
    annee_naissance,
    case
        when annee_naissance is null then null
        else extract(year from current_date)::int - annee_naissance
    end as age,
    case
        when annee_naissance is null then '?'
        when extract(year from current_date)::int - annee_naissance < 18 then '<18'
        when extract(year from current_date)::int - annee_naissance < 25 then '18-24'
        when extract(year from current_date)::int - annee_naissance < 35 then '25-34'
        when extract(year from current_date)::int - annee_naissance < 45 then '35-44'
        when extract(year from current_date)::int - annee_naissance < 55 then '45-54'
        else '55+'
    end as tranche_age
from calcule
