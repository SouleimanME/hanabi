-- Suite continue des mois couverts par l'activite, sans trou.
--
-- Une serie temporelle construite a partir des seules commandes saute les mois
-- vides : la courbe se resserre sur les periodes actives et laisse croire a une
-- activite continue. C'est exactement ce que `_last_months()` evite cote API,
-- en fabriquant les cles de mois independamment des donnees. Meme intention
-- ici, mais en SQL : les modeles gold partent de ce calendrier et joignent les
-- faits dessus, si bien qu'un mois sans commande apparait a zero plutot que de
-- disparaitre.
--
-- Les bornes viennent des donnees plutot que d'une fenetre glissante : le
-- calendrier couvre exactement l'histoire de la boutique, du premier
-- evenement enregistre au mois courant. C'est au tableau de bord de decider
-- combien de mois il affiche.
with bornes as (

    -- Le mois courant sert de valeur de repli a chaque borne : sur une base
    -- vide, le calendrier se reduit alors a une seule ligne au lieu de partir
    -- d'une date arbitraire ou de produire une serie inversee, donc vide.
    select
        least(
            coalesce((select min(mois_date) from {{ ref('slv_commandes') }}), date_trunc('month', current_date)::date),
            coalesce((select min(mois_inscription_date) from {{ ref('slv_clients') }}), date_trunc('month', current_date)::date),
            coalesce((select min(mois_date) from {{ ref('slv_vues_produit') }}), date_trunc('month', current_date)::date)
        ) as premier_mois,
        date_trunc('month', current_date)::date as dernier_mois

),

serie as (

    select generate_series(premier_mois, dernier_mois, interval '1 month')::date as mois_date
    from bornes

)

select
    mois_date,
    to_char(mois_date, 'YYYY-MM')   as mois,
    extract(year from mois_date)::int  as annee,
    extract(month from mois_date)::int as numero_mois,
    -- Rang du mois dans la serie, du plus ancien au plus recent. Sert aux
    -- calculs de tendance : une regression sur le rang suppose des intervalles
    -- reguliers, ce que ce calendrier garantit et qu'une suite de mois tiree
    -- des donnees ne garantirait pas.
    row_number() over (order by mois_date)::int as rang
from serie
