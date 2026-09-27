-- Une ligne par référence et par thème : de quoi parlent les avis approuvés,
-- et en quel sens. `part_des_avis` rapporte les mentions aux avis analysés de
-- la référence, pas à tous ses avis : un avis pas encore lu ne compte pas.
with analyses as (

    select avis.product_id as produit_id, count(*) as avis_analyses
    from {{ ref('brz_avis') }} as avis
    join {{ ref('brz_analyses_avis') }} as lecture
        on lecture.empreinte = md5(btrim(avis.text))
    where avis.approved
    group by avis.product_id

),

mentions as (

    select
        produit_id,
        theme,
        count(*)                                    as mentions,
        count(*) filter (where ton = 'positif')     as positives,
        count(*) filter (where ton = 'negatif')     as negatives,
        round(avg(note)::numeric, 2)                as note_moyenne
    from {{ ref('slv_themes_avis') }}
    where approuve
    group by produit_id, theme

)

select
    mentions.produit_id,
    produit.code,
    produit.name                                            as produit,
    produit.category                                        as categorie,
    mentions.theme,
    mentions.mentions::int                                  as mentions,
    mentions.positives::int                                 as positives,
    mentions.negatives::int                                 as negatives,
    round(mentions.negatives::numeric / mentions.mentions, 4) as taux_negatif,
    round(mentions.mentions::numeric / analyses.avis_analyses, 4) as part_des_avis,
    mentions.note_moyenne
from mentions
join analyses on analyses.produit_id = mentions.produit_id
join {{ ref('brz_produits') }} as produit on produit.id = mentions.produit_id
