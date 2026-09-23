-- La table des segments totalise la table des clients. Passe sans ligne rendue.
with segments as (

    select
        sum(clients)    as clients,
        sum(ca_cents)   as ca_cents
    from {{ ref('gold_segments_rfm') }}

),

clients as (

    select
        count(*)                as clients,
        sum(montant_cents)      as ca_cents
    from {{ ref('gold_clients_rfm') }}

)

select
    segments.clients    as clients_segments,
    clients.clients     as clients_detail,
    segments.ca_cents   as ca_segments,
    clients.ca_cents    as ca_detail
from segments
cross join clients
where segments.clients <> clients.clients
   or segments.ca_cents <> clients.ca_cents
