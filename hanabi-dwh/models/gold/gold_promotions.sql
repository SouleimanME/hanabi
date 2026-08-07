-- Rendement de chaque code promotionnel.
--
-- Part des codes declares et non des commandes, avec une jointure externe : un
-- code que personne n'a utilise doit apparaitre a zero. C'est meme le resultat
-- le plus utile de cette table - un code invisible parce qu'aucune commande ne
-- le mentionne est un code dont on ne saura jamais qu'il ne sert a rien.
with usage as (

    select
        code_promo,
        count(*)                as commandes,
        sum(total_cents)        as ca_cents,
        sum(remise_cents)       as remise_cents,
        count(distinct client_id) as clients,
        min(commandee_le)       as premiere_utilisation_le,
        max(commandee_le)       as derniere_utilisation_le
    from {{ ref('slv_commandes') }}
    where est_ca and code_promo is not null
    group by code_promo

)

select
    promo.code,
    promo.kind                                      as type_remise,
    promo.percent                                   as pourcentage,
    promo.amount_cents                              as montant_cents,
    promo.min_subtotal_cents                        as seuil_cents,
    promo.active                                    as actif,
    promo.expires_at                                as expire_le,

    coalesce(usage.commandes, 0)::int               as commandes,
    coalesce(usage.clients, 0)::int                 as clients,
    coalesce(usage.ca_cents, 0)::bigint             as ca_cents,
    coalesce(usage.remise_cents, 0)::bigint         as remise_cents,
    round(coalesce(usage.ca_cents, 0)::numeric
          / nullif(usage.commandes, 0))::bigint     as panier_moyen_cents,
    -- Ce que la remise a coute rapporte a ce qu'elle a fait entrer. Un ratio
    -- eleve signale un code qui rogne la marge sans faire de volume ; il ne dit
    -- pas si les commandes auraient eu lieu sans lui, ce qu'aucune donnee de
    -- cette table ne peut trancher.
    round(coalesce(usage.remise_cents, 0)::numeric
          / nullif(usage.ca_cents, 0), 4)           as cout_relatif,
    usage.premiere_utilisation_le,
    usage.derniere_utilisation_le
from {{ ref('brz_promos') }} as promo
left join usage on usage.code_promo = promo.code
order by coalesce(usage.ca_cents, 0) desc
