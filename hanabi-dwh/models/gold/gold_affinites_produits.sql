-- Règles d'association entre produits.
--
-- Support : part des commandes avec la paire. Confiance A vers B : part des
-- commandes avec A qui contiennent B. Lift : confiance rapportée à la fréquence
-- de B ; au-dessus de 1, les articles se complètent. Tri par lift.
with commandes_ca as (

    select commande_id from {{ ref('slv_commandes') }} where est_ca

),

-- Un article répété dans une commande ne forme qu'une paire
paniers as (

    select distinct commande_id, produit_id
    from {{ ref('slv_lignes_commande') }}
    where est_ca

),

total as (

    select count(*) as commandes from commandes_ca

),

par_produit as (

    select produit_id, count(*) as commandes
    from paniers
    group by produit_id

),

paires as (

    -- Chaque paire une fois, dans un ordre stable
    select
        a.produit_id    as produit_a_id,
        b.produit_id    as produit_b_id,
        count(*)        as commandes_communes
    from paniers as a
    inner join paniers as b
        on b.commande_id = a.commande_id
       and b.produit_id > a.produit_id
    group by a.produit_id, b.produit_id

)

select
    paires.produit_a_id,
    produit_a.name                                      as produit_a,
    paires.produit_b_id,
    produit_b.name                                      as produit_b,
    paires.commandes_communes::int,
    round(paires.commandes_communes::numeric / total.commandes, 4)          as support,
    round(paires.commandes_communes::numeric / compte_a.commandes, 4)       as confiance_ab,
    round(paires.commandes_communes::numeric / compte_b.commandes, 4)       as confiance_ba,
    round(
        (paires.commandes_communes::numeric / compte_a.commandes)
        / (compte_b.commandes::numeric / total.commandes),
        3
    )                                                                       as lift
from paires
cross join total
inner join par_produit as compte_a on compte_a.produit_id = paires.produit_a_id
inner join par_produit as compte_b on compte_b.produit_id = paires.produit_b_id
inner join {{ ref('brz_produits') }} as produit_a on produit_a.id = paires.produit_a_id
inner join {{ ref('brz_produits') }} as produit_b on produit_b.id = paires.produit_b_id
-- Seuil de bruit : 1 % des commandes, cinq au minimum
where paires.commandes_communes >= greatest(5, total.commandes / 100)
order by lift desc
