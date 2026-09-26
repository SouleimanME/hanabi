-- Thèmes et tons par texte d'avis, tels qu'écrits par ingestion/avis.py.
select
    empreinte,
    themes,
    version,
    modele,
    analyse_le
from {{ source('hanabi_externe', 'analyses_avis') }}
