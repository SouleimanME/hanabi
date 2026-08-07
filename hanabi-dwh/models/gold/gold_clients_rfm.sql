-- Segmentation Recence / Frequence / Montant, une ligne par client acheteur.
--
-- Trois questions : quand ce client a-t-il commande pour la derniere fois,
-- combien de fois, et pour quel montant. Le croisement des trois separe le
-- client fidele du client unique venu par une promotion, ce qu'aucun total ne
-- montre.
--
-- Les non-acheteurs sont exclus : ils n'ont ni recence ni montant, et les
-- inclure ecraserait la distribution des quintiles vers le bas.
--
-- Les scores sont relatifs, jamais absolus : un client est note par rapport aux
-- autres clients de cette boutique. Des seuils en euros ecrits en dur seraient
-- faux ailleurs, et faux ici des le premier changement de gamme. La contrepartie
-- est connue : sur une dizaine d'acheteurs, les quintiles ne separent plus rien.
-- Ce n'est pas un defaut du calcul mais sa nature - ce qu'il mesure est un rang.
--
-- Limite qui demeure : un groupe d'ex aequo plus gros qu'un quintile ne peut pas
-- etre reparti. Si la moitie des clients n'ont commande qu'une fois, cette
-- moitie partage forcement un score de frequence. C'est une propriete de la
-- donnee, pas du calcul, et aucune methode de notation ne la leve.
with base as (

    select
        commande.client_id,
        client.nom,
        client.email,
        client.ville,
        client.tranche_age,
        client.civilite,
        max(commande.commandee_le)                          as derniere_commande_le,
        current_date - max(commande.commandee_le)::date     as recence_jours,
        count(*)                                            as frequence,
        sum(commande.total_cents)                           as montant_cents
    from {{ ref('slv_commandes') }} as commande
    inner join {{ ref('slv_clients') }} as client
        on client.client_id = commande.client_id
    where commande.est_ca and commande.client_id is not null
    group by
        commande.client_id, client.nom, client.email,
        client.ville, client.tranche_age, client.civilite

),

positions as (

    -- Position de chaque client dans la population, sur les trois axes.
    --
    -- `cume_dist()` donne la part cumulee des clients situes a la hauteur du
    -- client courant ou avant lui, et attribue la meme valeur a tous les ex
    -- aequo - c'est ce qui garantit que deux clients au meme montant seront
    -- notes pareil, quel que soit l'ordre dans lequel la base rend les lignes.
    --
    -- On lui retranche ensuite la moitie du poids du groupe pour viser son
    -- milieu plutot que sa fin. La moitie des clients n'ayant commande qu'une
    -- fois, juger ce groupe sur son extremite la plus defavorable le
    -- deprecierait tout entier ; la convention des rangs moyens est la reponse
    -- usuelle a ce probleme.
    select
        *,
        cume_dist() over (order by recence_jours asc)
            - (count(*) over (partition by recence_jours))::numeric
              / (2 * count(*) over ())                          as milieu_r,
        cume_dist() over (order by frequence desc)
            - (count(*) over (partition by frequence))::numeric
              / (2 * count(*) over ())                          as milieu_f,
        cume_dist() over (order by montant_cents desc)
            - (count(*) over (partition by montant_cents))::numeric
              / (2 * count(*) over ())                          as milieu_m
    from base

),

scores as (

    -- Quintiles de population : le milieu du groupe, ramene sur cinq tranches.
    --
    -- Le decoupage porte sur la population et non sur l'echelle des valeurs.
    -- La version precedente classait les valeurs distinctes : avec 679
    -- anciennetes differentes, un score de recence a 5 voulait dire « dans les
    -- 136 premieres valeurs de l'echelle » et non « parmi les 20 % de clients
    -- les plus recents ». La clientele etant concentree sur les achats
    -- recents, 73 % des acheteurs decrochaient un 5 et les segments batis sur
    -- une mauvaise recence se vidaient - dix-neuf personnes sur trente-quatre
    -- mille dans « A risque », la ou la relance a pourtant le plus de valeur.
    --
    -- `least(4, ...)` borne la derniere tranche, que `floor` ferait deborder
    -- si un milieu valait exactement 1. Tranche 0 = la meilleure, donc 5.
    --
    -- Ce calcul doit rester identique a `_score_par_rang` dans
    -- `hanabi-back/app/analytics.py`. Les deux notent la meme clientele ; s'ils
    -- divergeaient, le back-office afficherait deux segmentations
    -- contradictoires selon l'onglet ouvert.
    select
        *,
        5 - least(4, floor(milieu_r * 5)::int) as r,
        5 - least(4, floor(milieu_f * 5)::int) as f,
        5 - least(4, floor(milieu_m * 5)::int) as m
    from positions

)

select
    client_id,
    nom,
    email,
    ville,
    tranche_age,
    civilite,
    recence_jours::int,
    frequence::int,
    montant_cents::bigint,
    round(montant_cents::numeric / nullif(frequence, 0))::bigint as panier_moyen_cents,
    derniere_commande_le,
    r,
    f,
    m,
    -- Les trois scores concatenes, notation d'usage dans les outils de gestion
    -- de la relation client : « 555 » se lit d'un coup d'oeil, la ou trois
    -- colonnes demandent d'etre recomposees mentalement.
    (r::text || f::text || m::text)                             as score_rfm,

    -- Sept segments plutot que les 125 combinaisons possibles : un decoupage
    -- grossier qu'une equipe s'approprie vaut mieux qu'une grille exhaustive
    -- que personne ne lit. Les frontieres sont celles couramment retenues, pas
    -- une verite.
    --
    -- Le nombre reel de commandes intervient a cote du score de frequence. Un
    -- client venu une seule fois, meme pour un gros montant recent, n'est pas
    -- fidele : il est nouveau. Se fier au seul score de frequence le classait
    -- parmi les fideles des que son montant tirait la moyenne vers le haut, et
    -- gonflait ainsi le segment le plus flatteur.
    case
        when frequence >= 2 and r >= 4 and (f + m) / 2.0 >= 4 then 'Champions'
        when frequence >= 2 and r >= 3 and (f + m) / 2.0 >= 3 then 'Fideles'
        when frequence  = 1 and r >= 4                        then 'Nouveaux'
        when r >= 3                                           then 'Prometteurs'
        -- Bon client qui ne revient plus : c'est ici que la relance a le plus de
        -- valeur, puisqu'il a deja prouve qu'il achetait.
        when (f + m) / 2.0 >= 3                               then 'A risque'
        when (f + m) / 2.0 <= 2 and r <= 2                    then 'Endormis'
        else 'A reactiver'
    end as segment
from scores
