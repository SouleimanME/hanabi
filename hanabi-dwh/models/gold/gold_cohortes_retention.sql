-- Retention par cohorte d'inscription, sous forme longue.
--
-- Une ligne par couple (cohorte, decalage) plutot qu'une matrice a colonnes
-- fixes : le nombre de colonnes d'une matrice depend de la profondeur
-- d'historique, donc changerait a chaque mois qui passe. La forme longue se
-- pivote a l'affichage et se filtre en SQL, ce qu'une matrice ne permet ni l'un
-- ni l'autre.
--
-- C'est la seule vue qui distingue une croissance saine d'une fuite en avant :
-- une boutique qui recrute beaucoup et retient mal affiche une belle courbe de
-- chiffre d'affaires et des colonnes qui s'effondrent des le premier mois.
--
-- Les couples situes dans le futur d'une cohorte recente sont absents, et non a
-- zero : une cohorte d'un mois n'a pas encore eu l'occasion de revenir six mois
-- plus tard, et l'ecrire a zero la ferait passer pour un echec.
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

    -- Produit de chaque cohorte par les mois qui la suivent, jusqu'au mois
    -- courant inclus. Passer par le calendrier plutot que par les seuls mois ou
    -- il y a eu des commandes garantit qu'un mois creux ressort a zero et non
    -- comme une case absente : sur une courbe de retention, une case manquante
    -- et une case a zero racontent deux histoires opposees.
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
    -- Le mois 0 mesure la conversion a l'inscription, les suivants la
    -- fidelisation. Les deux se lisent sur la meme echelle, ce qui explique que
    -- la premiere colonne d'une table de retention soit toujours la plus haute.
    round(coalesce(activite.clients_actifs, 0)::numeric
          / nullif(grille.taille, 0), 4)        as taux_retention
from grille
left join activite
    on activite.cohorte_date = grille.cohorte_date
   and activite.mois_activite = grille.mois_activite
order by grille.cohorte_date, grille.decalage_mois
