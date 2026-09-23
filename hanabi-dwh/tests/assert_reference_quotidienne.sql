-- La référence d'un jour ne dépend pas du mode de construction : recalculée sur la
-- table entière, elle doit redonner la valeur écrite. Une fenêtre qui ne voyait que
-- les jours reconstruits laissait sans référence les premiers jours de chaque
-- passage incrémental ; chaque jour finissait par l'être.
with recalcul as (

    select
        jour,
        ca_reference_cents,
        avg(ca_cents) over (
            partition by nature_jour
            order by jour
            rows between 4 preceding and 1 preceding
        )::bigint as attendu
    from {{ ref('gold_ca_quotidien') }}

)

select jour, ca_reference_cents, attendu
from recalcul
where ca_reference_cents is distinct from attendu
