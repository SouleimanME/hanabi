-- Consultations de fiche produit, telles qu'ecrites par l'application.
--
-- La table ne contient ni adresse IP ni empreinte de navigateur : l'API n'en
-- enregistre pas. `user_id` est nul pour un visiteur non connecte, et la ligne
-- est alors strictement anonyme. L'entrepot n'a donc rien a anonymiser ici -
-- il n'y a rien a anonymiser, ce qui est la bonne facon de traiter le sujet.
select
    id,
    product_id,
    user_id,
    created_at
from {{ source('hanabi_oltp', 'product_views') }}
