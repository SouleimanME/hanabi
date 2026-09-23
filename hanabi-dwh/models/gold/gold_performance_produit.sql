-- Une ligne par référence : audience, ventes, marge, avis, stock, classe ABC.
-- Équivalent SQL de `analytics.catalogue()`, non trié.
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
        -- Trois exemplaires d'un article font une seule commande
        count(distinct commande_id)         as commandes,
        max(commandee_le)                   as derniere_commande_le,
        bool_or(cout_connu)                 as cout_connu
    from {{ ref('slv_lignes_commande') }}
    where est_ca
    group by produit_id

),

ecoulement as (

    -- Vitesse sur une fenêtre glissante, pour refléter le rythme actuel
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
        -- Jours couverts par le stock ; NULL si la référence ne se vend plus
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
        -- Nul sans coût renseigné (et non 100 %)
        case
            when not cout_connu then 0
            else round(marge_cents::numeric / nullif(ca_cents, 0), 4)
        end as taux_marge,

        -- Classement ABC sur la marge. Cumul pris avant la référence (`1 preceding`) :
        -- celle qui franchit le seuil reste dans la classe qu'elle complète.
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
        -- Marge totale nulle ou négative : tout en C
        when part_marge is null then 'C'
        when part_cumulee_avant < 0.80 then 'A'
        when part_cumulee_avant < 0.95 then 'B'
        else 'C'
    end as classe_abc
from classe
