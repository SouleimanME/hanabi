-- Regles d'association entre produits : ce qui s'achete avec quoi.
--
-- Trois mesures, qui ne disent pas la meme chose :
--
--   le support     part des commandes contenant les deux articles. Il dit si la
--                  regle est frequente, pas si elle est interessante ;
--   la confiance   part des commandes contenant A qui contiennent aussi B. Elle
--                  se laisse tromper par les articles populaires : tout se vend
--                  avec le best-seller ;
--   le lift        rapporte la confiance a la frequence de B seul, et corrige
--                  ainsi ce biais. Au-dessus de 1, les deux articles s'achetent
--                  ensemble plus souvent que le hasard ne le voudrait ; en
--                  dessous, ils se substituent l'un a l'autre.
--
-- Seul le lift merite d'etre trie, d'ou l'ordre choisi.
--
-- C'est le calcul que `analytics.py` signalait lui-meme comme devant « redescendre
-- en SQL, voire dans une table precalculee » sur un catalogue plus fourni :
-- l'auto-jointure coute le carre du nombre d'articles par commande, et la faire
-- a chaque ouverture du tableau de bord ne tient que sur un petit catalogue.
-- C'est fait ici, une fois par construction.
with commandes_ca as (

    select commande_id from {{ ref('slv_commandes') }} where est_ca

),

-- Les doublons sont ecartes des le depart : trois exemplaires du meme article
-- dans une commande formeraient sinon trois fois la meme paire, et gonfleraient
-- support et confiance sans qu'aucune commande supplementaire n'existe.
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

    -- `a.produit_id < b.produit_id` ne produit chaque paire qu'une fois, dans un
    -- ordre stable. Sans cette inegalite stricte, on obtiendrait la paire dans
    -- les deux sens plus l'article avec lui-meme.
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
-- Seuil de bruit : au moins 1 % des commandes, et jamais moins de cinq. Sur une
-- dizaine de commandes communes, un lift eleve ne veut rien dire - c'est une
-- coincidence presentee comme une regle.
where paires.commandes_communes >= greatest(5, total.commandes / 100)
order by lift desc
