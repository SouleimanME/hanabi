-- Codes promotionnels, tels qu'ecrits par l'application.
--
-- Table de reference plus que table de faits : elle sert a rapprocher un code
-- releve sur une commande de la remise qu'il accordait, et surtout a faire
-- apparaitre les codes qui n'ont jamais servi - qu'aucune commande ne
-- mentionne, et qui seraient donc invisibles dans une analyse partie des
-- commandes seules.
select
    id,
    code,
    kind,
    percent,
    amount_cents,
    min_subtotal_cents,
    active,
    expires_at
from {{ source('hanabi_oltp', 'promos') }}
