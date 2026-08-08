{{
    config(
        materialized='incremental',
        unique_key='jour',
        incremental_strategy='delete+insert',
    )
}}

-- Chiffre d'affaires quotidien, replace dans son calendrier et dans sa devise.
--
-- C'est le premier modele a consommer les sources externes. Sans lui, le taux
-- de change et les jours feries seraient de la plomberie : charges, propres, et
-- utiles a personne. Deux questions y trouvent enfin une reponse.
--
-- « CETTE JOURNEE EST-ELLE MAUVAISE ? » Un 1er mai a quinze pour cent du volume
-- habituel n'est pas un incident, c'est un jour ferie. Comparer une journee a
-- la moyenne de toutes les journees melange des jours ouvres, des week-ends et
-- des feries ; on la compare donc a la moyenne des journees de MEME NATURE sur
-- les quatre semaines precedentes. Une detection d'anomalie batie sur la
-- moyenne brute sonne tous les lundis de Pentecote et se fait ignorer.
--
-- « LA MARGE BOUGE-T-ELLE PARCE QUE LES PRIX ONT BOUGE, OU PARCE QUE LE YEN A
-- BOUGE ? » Le cout fournisseur est libelle en yen et fige en euros a l'achat,
-- ce qui est voulu : un mois clos ne se reecrit pas. Mais du coup, une marge
-- qui se degrade ne dit pas d'ou vient la degradation. En exprimant le cout au
-- taux du jour puis a un taux de reference fixe, l'ecart entre les deux est
-- exactement l'effet de change, et ce qui reste est l'effet prix.
--
-- POURQUOI CE MODELE EST INCREMENTAL, ET POURQUOI LES MODELES RFM NE LE SONT
-- PAS. Une journee close ne change plus, a une exception pres : un
-- remboursement tardif fait sortir une commande du chiffre d'affaires des
-- semaines apres coup. On ne recalcule donc pas tout, mais on ne se contente
-- pas non plus des jours nouveaux : une fenetre de rattrapage reprend les
-- trente derniers jours a chaque execution.
--
-- Les modeles RFM, eux, ne peuvent pas etre incrementaux. La recence se mesure
-- par rapport a aujourd'hui : la ligne de CHAQUE client change chaque nuit,
-- meme celle d'un client qui n'a rien fait depuis deux ans. Un incremental y
-- serait plus qu'inutile, il serait faux, et il figerait des scores perimes en
-- donnant l'illusion de la fraicheur.
--
-- `delete+insert` plutot que `merge` : la cle est la journee, la fenetre de
-- rattrapage est contigue, et supprimer la plage avant de la reinserer coute
-- moins qu'un rapprochement ligne a ligne sur des milliers de cles.

{% set fenetre_rattrapage_jours = 30 %}

-- Taux de reference : la cotation la plus ancienne de la serie. Le choix de la
-- base importe peu, seule sa stabilite compte - c'est l'ecart qui est lu, pas
-- le niveau. La figer dans le modele plutot que la recalculer evite qu'une
-- reconstruction change retroactivement l'effet de change de 2024.
{% set taux_reference = 165.0 %}

with jours as (

    select
        jour,
        jour_semaine,
        week_end,
        ferie_fr,
        ferie_jp,
        feries_nom,
        ouvre_fr,
        taux_jpy,
        taux_reporte
    from {{ ref('slv_calendrier_quotidien') }}
    where jour <= current_date

    {% if is_incremental() %}
        -- La fenetre de rattrapage part du plus ancien jour deja construit
        -- moins l'intervalle : sans le `coalesce`, une table vide produirait
        -- un `null` et la clause laisserait passer zero ligne.
        and jour >= coalesce(
            (select max(jour) from {{ this }}) - interval '{{ fenetre_rattrapage_jours }} days',
            '1900-01-01'::date
        )
    {% endif %}

),

ventes as (

    select
        jour,
        count(*)                    as commandes,
        count(distinct client_id)   as acheteurs,
        sum(total_cents)            as ca_cents,
        sum(remise_cents)           as remise_cents
    from {{ ref('slv_commandes') }}
    where est_ca
      and jour in (select jour from jours)
    group by jour

),

couts as (

    -- Les lignes portent deja leur journee et leur drapeau de chiffre
    -- d affaires : les rejoindre aux commandes ne servirait qu a relire la
    -- meme information deux fois.
    select
        jour,
        sum(cout_cents) as cout_cents
    from {{ ref('slv_lignes_commande') }}
    where est_ca
      and jour in (select jour from jours)
    group by jour

),

assemble as (

    select
        j.jour,
        j.jour_semaine,
        j.week_end,
        j.ferie_fr,
        j.ferie_jp,
        j.feries_nom,
        j.ouvre_fr,
        j.taux_jpy,
        j.taux_reporte,

        coalesce(v.commandes, 0)    as commandes,
        coalesce(v.acheteurs, 0)    as acheteurs,
        coalesce(v.ca_cents, 0)     as ca_cents,
        coalesce(v.remise_cents, 0) as remise_cents,
        coalesce(c.cout_cents, 0)   as cout_cents,

        -- La nature d'une journee, pour ne comparer que ce qui est comparable.
        case
            when j.ferie_fr then 'ferie'
            when j.week_end then 'week-end'
            else 'ouvre'
        end as nature_jour

    from jours j
    left join ventes v on v.jour = j.jour
    left join couts  c on c.jour = j.jour

)

select
    jour,
    jour_semaine,
    nature_jour,
    week_end,
    ferie_fr,
    ferie_jp,
    feries_nom,
    ouvre_fr,

    commandes,
    acheteurs,
    ca_cents,
    remise_cents,
    cout_cents,
    ca_cents - cout_cents as marge_cents,

    taux_jpy,
    taux_reporte,

    -- Cout exprime en yen au taux du jour, puis ce que ce meme cout aurait
    -- valu au taux de reference. La difference des deux marges isole l'effet
    -- de change ; ce qui reste dans la marge est l'effet prix.
    round(cout_cents * taux_jpy / 100.0)                     as cout_jpy,
    round(ca_cents - cout_cents * ({{ taux_reference }} / taux_jpy)) as marge_change_constant_cents,

    -- Reference de comparaison : la moyenne des quatre journees de meme nature
    -- qui precedent. `rows` et non `range` : on veut les quatre occurrences
    -- precedentes de cette nature, pas les quatre dernieres semaines de
    -- calendrier, qui n'en contiennent pas toujours quatre.
    avg(ca_cents) over (
        partition by nature_jour
        order by jour
        rows between 4 preceding and 1 preceding
    )::bigint as ca_reference_cents

from assemble
