-- Une ligne par avis et par thème relevé. Le texte est rejoint par la même
-- empreinte que celle de l'ingestion : un texte porté par dix avis compte dix fois.
select
    avis.id                                 as avis_id,
    avis.product_id                         as produit_id,
    avis.rating                             as note,
    avis.approved                           as approuve,
    avis.created_at::date                   as jour,
    to_char(avis.created_at, 'YYYY-MM')     as mois,
    element ->> 'theme'                     as theme,
    element ->> 'ton'                       as ton
from {{ ref('brz_avis') }} as avis
join {{ ref('brz_analyses_avis') }} as lecture
    on lecture.empreinte = md5(btrim(avis.text))
cross join lateral jsonb_array_elements(lecture.themes) as element
