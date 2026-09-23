-- Segmentation RFM, une ligne par client acheteur, désigné par son identifiant.
--
-- Scores relatifs (quintiles de population), non-acheteurs exclus. Un groupe
-- d'ex aequo plus gros qu'un quintile partage forcément son score.
with base as (

    select
        commande.client_id,
        client.ville,
        client.tranche_age,
        client.civilite,
        max(commande.commandee_le)                          as derniere_commande_le,
        current_date - max(commande.commandee_le)::date     as recence_jours,
        count(*)                                            as frequence,
        sum(commande.total_cents)                           as montant_cents
    from {{ ref('slv_commandes') }} as commande
    inner join {{ ref('slv_clients') }} as client
        on client.client_id = commande.client_id
    where commande.est_ca and commande.client_id is not null
    group by
        commande.client_id, client.ville, client.tranche_age, client.civilite

),

positions as (

    -- Position dans la population sur chaque axe : `cume_dist()` donne la même
    -- valeur aux ex aequo, moins la moitié du groupe pour viser son milieu.
    select
        *,
        cume_dist() over (order by recence_jours asc)
            - (count(*) over (partition by recence_jours))::numeric
              / (2 * count(*) over ())                          as milieu_r,
        cume_dist() over (order by frequence desc)
            - (count(*) over (partition by frequence))::numeric
              / (2 * count(*) over ())                          as milieu_f,
        cume_dist() over (order by montant_cents desc)
            - (count(*) over (partition by montant_cents))::numeric
              / (2 * count(*) over ())                          as milieu_m
    from base

),

scores as (

    -- Quintiles de population, tranche 0 = score 5. `least(4, ...)` borne un milieu égal à 1.
    -- Classer les valeurs distinctes donnait R=5 à 73 % des acheteurs.
    -- Doit rester identique à `_score_par_rang` (hanabi-back/app/analytics.py).
    select
        *,
        5 - least(4, floor(milieu_r * 5)::int) as r,
        5 - least(4, floor(milieu_f * 5)::int) as f,
        5 - least(4, floor(milieu_m * 5)::int) as m
    from positions

)

select
    client_id,
    ville,
    tranche_age,
    civilite,
    recence_jours::int,
    frequence::int,
    montant_cents::bigint,
    round(montant_cents::numeric / nullif(frequence, 0))::bigint as panier_moyen_cents,
    derniere_commande_le,
    r,
    f,
    m,
    -- Notation usuelle « 555 »
    (r::text || f::text || m::text)                             as score_rfm,

    -- Sept segments ; le nombre réel de commandes s'ajoute au score F : une seule
    -- commande fait un client nouveau, pas fidèle.
    case
        when frequence >= 2 and r >= 4 and (f + m) / 2.0 >= 4 then 'Champions'
        when frequence >= 2 and r >= 3 and (f + m) / 2.0 >= 3 then 'Fideles'
        when frequence  = 1 and r >= 4                        then 'Nouveaux'
        when r >= 3                                           then 'Prometteurs'
        -- Bon client qui ne revient plus
        when (f + m) / 2.0 >= 3                               then 'A risque'
        when (f + m) / 2.0 <= 2 and r <= 2                    then 'Endormis'
        else 'A reactiver'
    end as segment
from scores
