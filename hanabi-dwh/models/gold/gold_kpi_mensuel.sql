-- Serie mensuelle des indicateurs de la boutique.
--
-- Part du calendrier et joint les faits dessus, jamais l'inverse : un mois sans
-- commande doit ressortir a zero. Une serie construite depuis les commandes
-- sauterait ce mois, et la courbe donnerait a lire une activite continue la ou
-- il y a eu un creux.
--
-- Les quatre sources sont agregees separement avant d'etre rapprochees. Les
-- joindre d'abord multiplierait les lignes - trois vues pour une commande
-- feraient compter la commande trois fois - et c'est la faute la plus courante
-- dans ce genre de table.
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

    -- `nullif` plutot qu'un CASE : une division par zero rendrait NULL de toute
    -- facon, autant l'ecrire une fois. NULL et non zero, parce qu'un panier
    -- moyen sur zero commande n'existe pas - l'afficher a 0 EUR ferait croire a
    -- un effondrement la ou il n'y a simplement rien a mesurer.
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
order by calendrier.mois_date
