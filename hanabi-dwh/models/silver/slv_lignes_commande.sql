{{ config(materialized='table') }}

-- Table de faits centrale : une ligne par article commande, deja rapprochee de
-- son en-tete et de sa fiche produit.
--
-- Seul modele silver materialise en table, et non en vue. Sept des huit modeles
-- gold s'appuient dessus ; en vue, la jointure des trois tables serait rejouee
-- sept fois a chaque construction. Le calcul est fait une fois, ecrit, puis
-- relu - c'est le seul endroit du projet ou la duplication de donnees se paie
-- vraiment, et elle se rembourse immediatement.
--
-- La marge s'appuie sur `unit_price_cents` et `unit_cost_cents`, figes dans la
-- ligne au moment de l'achat, jamais sur les valeurs courantes de la fiche. Un
-- changement de tarif fournisseur ne doit pas reecrire le resultat des mois
-- deja clos.
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
    produit.category                                    as categorie,
    -- Nom fige a l'achat. Differe du nom courant quand la fiche a ete renommee
    -- depuis, ce qui est en soi une information pour qui relit un historique.
    ligne.name                                          as produit_a_l_achat,

    ligne.qty                                           as quantite,
    ligne.unit_price_cents                              as prix_unitaire_cents,
    ligne.unit_cost_cents                               as cout_unitaire_cents,
    ligne.qty * ligne.unit_price_cents                  as ca_cents,
    ligne.qty * ligne.unit_cost_cents                   as cout_cents,
    ligne.qty * (ligne.unit_price_cents - ligne.unit_cost_cents) as marge_cents,
    -- Faux quand le cout d'achat n'a pas ete renseigne. Sans ce drapeau, une
    -- fiche mal remplie afficherait 100 % de marge et passerait pour la plus
    -- rentable du catalogue - exactement le contresens que le back-office
    -- evite deja de son cote.
    ligne.unit_cost_cents > 0                           as cout_connu
from {{ ref('brz_lignes_commande') }} as ligne
inner join {{ ref('slv_commandes') }} as commande
    on commande.commande_id = ligne.order_id
inner join {{ ref('brz_produits') }} as produit
    on produit.id = ligne.product_id
