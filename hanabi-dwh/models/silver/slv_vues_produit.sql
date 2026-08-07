-- Consultations de fiche, avec leurs periodes de rattachement.
--
-- Table de loin la plus volumineuse de l'entrepot. Elle reste une vue : les
-- modeles gold qui s'en servent l'agregent immediatement, si bien que
-- PostgreSQL n'a jamais a en materialiser le detail. La materialiser en table
-- reviendrait a recopier des centaines de milliers de lignes pour n'en relire
-- que des comptages.
select
    id                                      as vue_id,
    product_id                              as produit_id,
    user_id                                 as client_id,
    -- Une consultation sans compte rattache est le fait d'un visiteur non
    -- connecte. La distinction porte l'ecart entre audience totale et audience
    -- identifiee, que le rapport de conversion ne montre pas.
    user_id is not null                     as identifie,
    created_at                              as vue_le,
    created_at::date                        as jour,
    date_trunc('month', created_at)::date   as mois_date,
    to_char(created_at, 'YYYY-MM')          as mois
from {{ ref('brz_vues_produit') }}
