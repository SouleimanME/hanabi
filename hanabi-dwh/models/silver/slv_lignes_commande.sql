{{ config(materialized='table') }}

-- Table de faits : une ligne par article, avec commande et produit.
-- Matérialisée en table (cinq modèles gold la lisent). Marge sur prix et coût figés à l'achat.
select
    ligne.id                                            as ligne_id,
    ligne.order_id                                      as commande_id,
    ligne.product_id                                    as produit_id,

    commande.client_id,
    commande.statut,
    commande.est_ca,
    commande.commandee_le,
    commande.jour,
    commande.mois,
    commande.mois_date,
    commande.code_promo,

    produit.name                                        as produit,
    -- Nom et catégorie figés à l'achat : un objet reclassé ne déplace pas ses ventes passées
    ligne.category                                      as categorie,
    ligne.name                                          as produit_a_l_achat,

    ligne.qty                                           as quantite,
    ligne.unit_price_cents                              as prix_unitaire_cents,
    ligne.unit_cost_cents                               as cout_unitaire_cents,
    ligne.qty * ligne.unit_price_cents                  as ca_cents,
    ligne.qty * ligne.unit_cost_cents                   as cout_cents,
    ligne.qty * (ligne.unit_price_cents - ligne.unit_cost_cents) as marge_cents,
    -- Faux sans coût renseigné, pour ne pas afficher 100 % de marge
    ligne.unit_cost_cents > 0                           as cout_connu
from {{ ref('brz_lignes_commande') }} as ligne
inner join {{ ref('slv_commandes') }} as commande
    on commande.commande_id = ligne.order_id
inner join {{ ref('brz_produits') }} as produit
    on produit.id = ligne.product_id
