-- Commandes conformes : periodes calculees, appartenance au chiffre d'affaires.
--
-- `est_ca` porte ici la regle qui, cote API, est repetee dans une quinzaine de
-- requetes sous la forme `status in (...)`. Une regle metier ecrite quinze fois
-- est une regle metier qui finira par differer a un endroit : la ecrire une
-- fois, dans la couche conformee, est precisement ce que la couche silver
-- apporte.
--
-- Une commande annulee reste presente, avec `est_ca` a faux. C'est ce qui
-- permet de mesurer le taux d'annulation sans avoir a redescendre en bronze.
select
    id                                      as commande_id,
    number                                  as numero,
    user_id                                 as client_id,
    email,
    status                                  as statut,
    status in {{ statuts_ca() }}            as est_ca,
    subtotal_cents                          as sous_total_cents,
    discount_cents                          as remise_cents,
    shipping_cents                          as port_cents,
    total_cents                             as total_cents,
    promo_code                              as code_promo,
    created_at                              as commandee_le,
    created_at::date                        as jour,
    date_trunc('month', created_at)::date   as mois_date,
    to_char(created_at, 'YYYY-MM')          as mois
from {{ ref('brz_commandes') }}
