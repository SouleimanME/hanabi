-- Une ligne par reference : audience, ventes, marge, satisfaction, stock.
--
-- Reprend ce que `analytics.catalogue()` calcule en Python a chaque affichage
-- du tableau de bord, mais une fois pour toutes et en SQL. Le classement ABC,
-- qui exigeait un tri Python sur toutes les lignes, tient ici dans une fonction
-- de fenetrage.
--
-- Table non triee sur le metier : « les plus vus », « les moins commandes »,
-- « ceux qui ne se vendent pas » sont autant de tris de la meme matiere. Les
-- figer ici reviendrait a decider a la place de qui interroge.
with audience as (

    select produit_id, count(*) as vues
    from {{ ref('slv_vues_produit') }}
    group by produit_id

),

ventes as (

    select
        produit_id,
        sum(quantite)                       as unites,
        sum(ca_cents)                       as ca_cents,
        sum(marge_cents)                    as marge_cents,
        -- `count(distinct commande_id)` et non `count(*)` : une commande de
        -- trois exemplaires du meme article reste une commande. Confondre les
        -- deux gonflerait le taux de conversion des produits achetes par lot.
        count(distinct commande_id)         as commandes,
        max(commandee_le)                   as derniere_commande_le,
        bool_or(cout_connu)                 as cout_connu
    from {{ ref('slv_lignes_commande') }}
    where est_ca
    group by produit_id

),

ecoulement as (

    -- Vitesse mesuree sur une fenetre glissante et non sur tout l'historique :
    -- la couverture de stock doit refleter le rythme actuel, pas la moyenne
    -- depuis l'ouverture de la boutique.
    select
        produit_id,
        sum(quantite)::numeric / {{ var('fenetre_velocite_jours') }} as unites_par_jour
    from {{ ref('slv_lignes_commande') }}
    where est_ca
      and commandee_le >= current_date - interval '{{ var("fenetre_velocite_jours") }} days'
    group by produit_id

),

notes as (

    select
        produit_id,
        round(avg(note)::numeric, 2) as note_moyenne,
        count(*)                     as avis
    from {{ ref('slv_avis') }}
    where approuve
    group by produit_id

),

assemble as (

    select
        produit.id                                  as produit_id,
        produit.code,
        produit.name                                as produit,
        produit.category                            as categorie,
        produit.active                              as actif,
        produit.price_cents                         as prix_cents,
        produit.cost_cents                          as cout_cents,
        produit.stock,

        coalesce(audience.vues, 0)::int             as vues,
        coalesce(ventes.commandes, 0)::int          as commandes,
        coalesce(ventes.unites, 0)::int             as unites,
        coalesce(ventes.ca_cents, 0)::bigint        as ca_cents,
        coalesce(ventes.marge_cents, 0)::bigint     as marge_cents,
        coalesce(ventes.cout_connu, false)          as cout_connu,
        ventes.derniere_commande_le,

        round(coalesce(ventes.commandes, 0)::numeric
              / nullif(audience.vues, 0), 4)        as taux_conversion,
        round(coalesce(ecoulement.unites_par_jour, 0), 2) as unites_par_jour,
        -- Nombre de jours que le stock couvre encore. NULL quand la reference
        -- ne se vend plus du tout : la couverture est alors infinie, ce qui est
        -- un probleme d'une autre nature qu'une rupture imminente et ne doit pas
        -- se ranger a cote dans un tri.
        round(produit.stock / nullif(ecoulement.unites_par_jour, 0), 1) as couverture_jours,

        coalesce(notes.note_moyenne, 0)             as note_moyenne,
        coalesce(notes.avis, 0)::int                as avis
    from {{ ref('brz_produits') }} as produit
    left join audience   on audience.produit_id = produit.id
    left join ventes     on ventes.produit_id = produit.id
    left join ecoulement on ecoulement.produit_id = produit.id
    left join notes      on notes.produit_id = produit.id

),

classe as (

    select
        *,
        -- Taux de marge nul, et non 100 %, quand aucun cout n'est renseigne :
        -- une fiche mal remplie passerait sinon pour la plus rentable du
        -- catalogue.
        case
            when not cout_connu then 0
            else round(marge_cents::numeric / nullif(ca_cents, 0), 4)
        end as taux_marge,

        -- Classement ABC selon la loi de Pareto, sur la marge et non sur le
        -- chiffre d'affaires : c'est la marge qui paie les charges. Un article
        -- a fort volume et faible marge remplirait le haut d'un classement des
        -- ventes sans rien rapporter.
        --
        -- La part cumulee est prise AVANT la reference courante (`1 preceding`),
        -- pas apres. Autrement, celle qui fait franchir le seuil se retrouve
        -- exclue de la classe qu'elle vient de remplir : un catalogue ou un
        -- seul produit pese 85 % de la marge n'aurait aucune reference en A.
        coalesce(
            sum(marge_cents) over (
                order by marge_cents desc, produit_id
                rows between unbounded preceding and 1 preceding
            ), 0
        )::numeric / nullif(sum(marge_cents) over (), 0) as part_cumulee_avant,

        marge_cents::numeric
            / nullif(sum(marge_cents) over (), 0)        as part_marge
    from assemble

)

select
    produit_id,
    code,
    produit,
    categorie,
    actif,
    vues,
    commandes,
    unites,
    ca_cents,
    marge_cents,
    taux_marge,
    taux_conversion,
    prix_cents,
    cout_cents,
    stock,
    unites_par_jour,
    couverture_jours,
    note_moyenne,
    avis,
    derniere_commande_le,
    round(coalesce(part_marge, 0), 4)           as part_marge,
    round(coalesce(part_cumulee_avant, 0) + coalesce(part_marge, 0), 4) as part_cumulee,
    case
        -- Marge totale nulle ou negative : le classement n'a pas de sens, tout
        -- passe en C plutot que de repartir des references au hasard.
        when part_marge is null then 'C'
        when part_cumulee_avant < 0.80 then 'A'
        when part_cumulee_avant < 0.95 then 'B'
        else 'C'
    end as classe_abc
from classe
