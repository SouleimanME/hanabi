-- Date de la dernière construction, lue par le back-office.
-- `invocation_id` relie la ligne aux journaux dbt. Les dépendances déclarées
-- ci-dessous placent ce modèle en fin de graphe.
-- depends_on: {{ ref('gold_kpi_mensuel') }}
-- depends_on: {{ ref('gold_performance_produit') }}
-- depends_on: {{ ref('gold_clients_rfm') }}
-- depends_on: {{ ref('gold_cohortes_retention') }}
select
    current_timestamp                       as construit_le,
    '{{ invocation_id }}'                   as invocation_id,
    '{{ target.name }}'                     as environnement,
    '{{ var("statuts_ca") | join(", ") }}'  as statuts_ca
