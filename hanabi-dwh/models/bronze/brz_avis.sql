-- Avis clients, tels qu'ecrits par l'application.
--
-- Le texte de l'avis est conserve : contrairement a un visuel, il est court et
-- il est la matiere d'une lecture qualitative que le back-office peut vouloir
-- offrir un jour.
select
    id,
    product_id,
    user_id,
    author_name,
    rating,
    text,
    verified,
    approved,
    created_at
from {{ source('hanabi_oltp', 'reviews') }}
