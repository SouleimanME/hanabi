-- Catalogue, tel qu'ecrit par l'application.
--
-- `art` et `images` sont ecartes : ce sont des visuels, parfois une photo
-- entiere encodee en base64 sur plusieurs centaines de milliers de caracteres.
-- Les faire transiter par l'entrepot couterait cher et ne repondrait a aucune
-- question decisionnelle.
select
    id,
    code,
    name,
    category,
    blurb,
    price_cents,
    cost_cents,
    stock,
    is_new,
    active,
    featured
from {{ source('hanabi_oltp', 'products') }}
