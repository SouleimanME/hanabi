-- Rétention par cohorte d'inscription, en forme longue (cohorte, décalage).
-- Les décalages pas encore advenus sont absents, pas à zéro.
with cohortes as (

    select
        mois_inscription        as cohorte,
        mois_inscription_date   as cohorte_date,
        count(*)                as taille
    from {{ ref('slv_clients') }}
    group by mois_inscription, mois_inscription_date

),

activite as (

    select
        client.mois_inscription_date                        as cohorte_date,
        commande.mois_date                                  as mois_activite,
        count(distinct commande.client_id)                  as clients_actifs,
        sum(commande.total_cents)                           as ca_cents
    from {{ ref('slv_commandes') }} as commande
    inner join {{ ref('slv_clients') }} as client
        on client.client_id = commande.client_id
    where commande.est_ca
    group by client.mois_inscription_date, commande.mois_date

),

grille as (

    -- Chaque cohorte croisée avec les mois suivants : un mois creux sort à zéro
    select
        cohortes.cohorte,
        cohortes.cohorte_date,
        cohortes.taille,
        calendrier.mois_date        as mois_activite,
        calendrier.mois             as mois,
        (extract(year from calendrier.mois_date) - extract(year from cohortes.cohorte_date)) * 12
        + (extract(month from calendrier.mois_date) - extract(month from cohortes.cohorte_date))
                                    as decalage_mois
    from cohortes
    cross join {{ ref('slv_calendrier_mensuel') }} as calendrier
    where calendrier.mois_date >= cohortes.cohorte_date

)

select
    grille.cohorte,
    grille.cohorte_date,
    grille.taille::int                          as taille_cohorte,
    grille.decalage_mois::int,
    grille.mois                                 as mois_activite,
    coalesce(activite.clients_actifs, 0)::int   as clients_actifs,
    coalesce(activite.ca_cents, 0)::bigint      as ca_cents,
    -- Mois 0 : conversion à l'inscription ; suivants : fidélisation
    round(coalesce(activite.clients_actifs, 0)::numeric
          / nullif(grille.taille, 0), 4)        as taux_retention
from grille
left join activite
    on activite.cohorte_date = grille.cohorte_date
   and activite.mois_activite = grille.mois_activite
order by grille.cohorte_date, grille.decalage_mois
