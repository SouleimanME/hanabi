-- Les trois familles du catalogue, comparees sur les memes mesures.
--
-- Agrege `gold_performance_produit` plutot que de repartir des faits : la table
-- produit porte deja les vues, la marge et les notes, et la reconstruire
-- risquerait surtout d'aboutir a des totaux qui ne se recoupent pas d'une vue a
-- l'autre. Un tableau de bord ou la somme des categories ne fait pas le total
-- du catalogue perd toute credibilite, et c'est arrive a bien des projets pour
-- cette raison exacte.
select
    categorie,
    count(*)::int                                   as references,
    count(*) filter (where actif)::int              as references_actives,
    sum(vues)::int                                  as vues,
    sum(commandes)::int                             as commandes,
    sum(unites)::int                                as unites,
    sum(ca_cents)::bigint                           as ca_cents,
    sum(marge_cents)::bigint                        as marge_cents,
    round(sum(marge_cents)::numeric / nullif(sum(ca_cents), 0), 4) as taux_marge,
    round(sum(commandes)::numeric / nullif(sum(vues), 0), 4)       as taux_conversion,
    round(sum(ca_cents)::numeric / nullif(sum(vues), 0))::bigint   as ca_par_vue_cents,
    sum(stock)::int                                 as stock,
    -- Part de la categorie dans la marge totale, a comparer a sa part dans le
    -- chiffre d'affaires : c'est l'ecart entre les deux qui dit ou l'argent est
    -- reellement gagne.
    round(sum(marge_cents)::numeric
          / nullif(sum(sum(marge_cents)) over (), 0), 4)           as part_marge,
    round(sum(ca_cents)::numeric
          / nullif(sum(sum(ca_cents)) over (), 0), 4)              as part_ca
from {{ ref('gold_performance_produit') }}
group by categorie
order by sum(ca_cents) desc
