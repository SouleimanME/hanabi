-- Clients conformes : demographie normalisee, cohorte d'inscription.
--
-- L'age est deduit de la seule annee de naissance, a un an pres, exactement
-- comme le fait `analytics.py`. Le raccourci deplace une poignee de comptes
-- d'une tranche a l'autre ; le repeter ici n'est pas une negligence, c'est la
-- condition pour que l'entrepot et le tableau de bord historique comptent la
-- meme chose. Deux decoupages differents pour la meme population donneraient
-- deux histogrammes contradictoires, et personne ne saurait lequel croire.
--
-- Les administrateurs sont conserves. Ils faussent marginalement les comptages
-- de clientele, mais les exclure ici les ferait disparaitre de l'entrepot sans
-- qu'aucune vue ne le signale ; c'est aux modeles gold de les ecarter quand
-- c'est pertinent.
with source as (

    select * from {{ ref('brz_clients') }}

),

calcule as (

    select
        id                                          as client_id,
        name                                        as nom,
        email,
        city                                        as ville,
        cp                                          as code_postal,
        is_admin                                    as est_admin,
        created_at                                  as inscrit_le,
        date_trunc('month', created_at)::date       as mois_inscription_date,
        to_char(created_at, 'YYYY-MM')              as mois_inscription,

        -- « ? » plutot que NULL pour une civilite absente : c'est une modalite
        -- en soi dans les repartitions du back-office, pas un trou a masquer.
        coalesce(nullif(civility, ''), '?')         as civilite,

        -- `birthdate` est un texte 'AAAA-MM-JJ' cote application. Une saisie
        -- incoherente ne doit pas faire echouer la construction de l'entrepot :
        -- on ne prend les quatre premiers caracteres que s'ils forment bien
        -- quatre chiffres, et la ligne tombe sinon dans la tranche inconnue.
        case
            when birthdate ~ '^\d{4}' then substring(birthdate from 1 for 4)::int
        end                                         as annee_naissance
    from source

)

select
    client_id,
    nom,
    email,
    ville,
    code_postal,
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
