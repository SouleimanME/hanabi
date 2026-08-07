-- La table des segments doit totaliser exactement la table des clients.
--
-- `gold_segments_rfm` agrege `gold_clients_rfm`. Rien ne garantit que
-- l'agregation n'ait pas perdu ou double des lignes - un `where` oublie, une
-- jointure ajoutee plus tard - et le symptome serait invisible : sept lignes
-- plausibles, des pourcentages qui totalisent 100 %, et un effectif faux.
--
-- C'est la verification qu'on fait a la main la premiere fois, puis qu'on
-- oublie de refaire. Ecrite ici, elle est rejouee a chaque construction.
--
-- Un test dbt passe quand il ne rend aucune ligne.
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
