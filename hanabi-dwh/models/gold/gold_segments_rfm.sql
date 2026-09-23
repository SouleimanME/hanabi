-- Segments RFM : effectif et part du chiffre. `rang` fixe l'ordre d'affichage.
with agrege as (

    select
        segment,
        count(*)                                        as clients,
        sum(montant_cents)                              as ca_cents,
        round(avg(montant_cents))::bigint               as valeur_moyenne_cents,
        round(avg(frequence), 2)                        as commandes_moyennes,
        round(avg(recence_jours))::int                  as recence_moyenne_jours
    from {{ ref('gold_clients_rfm') }}
    group by segment

)

select
    segment,
    case segment
        when 'Champions'    then 1
        when 'Fideles'      then 2
        when 'Prometteurs'  then 3
        when 'Nouveaux'     then 4
        when 'A risque'     then 5
        when 'A reactiver'  then 6
        when 'Endormis'     then 7
        else 8
    end                                                 as rang,
    clients::int,
    round(clients::numeric / nullif(sum(clients) over (), 0), 4)    as part_clients,
    ca_cents::bigint,
    round(ca_cents::numeric / nullif(sum(ca_cents) over (), 0), 4)  as part_ca,
    valeur_moyenne_cents,
    commandes_moyennes,
    recence_moyenne_jours
from agrege
order by rang
