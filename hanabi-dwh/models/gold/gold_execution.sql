-- Journal de la derniere construction de l'entrepot.
--
-- Une ligne, reecrite a chaque `dbt run`. Sans elle, le back-office afficherait
-- des agregats sans pouvoir dire de quand ils datent - et c'est la question
-- qu'on se pose immediatement devant un chiffre qui ne bouge pas. Un entrepot
-- construit par lots est fatalement en retard sur la base transactionnelle ;
-- le probleme n'est pas ce retard, c'est de ne pas savoir de combien.
--
-- `invocation_id` est l'identifiant que dbt attribue a l'execution. Il relie la
-- ligne aux journaux et aux artefacts de `target/` en cas d'ecart constate.
--
-- Les dependances declarees ci-dessous ne sont pas utilisees par la requete :
-- elles servent uniquement a placer ce modele en fin de graphe. Sans elles, dbt
-- le construirait en premier - il ne lit rien - et l'horodatage annoncerait le
-- debut de la construction plutot que la date des donnees publiees.
-- depends_on: {{ ref('gold_kpi_mensuel') }}
-- depends_on: {{ ref('gold_performance_produit') }}
-- depends_on: {{ ref('gold_clients_rfm') }}
-- depends_on: {{ ref('gold_cohortes_retention') }}
select
    current_timestamp                       as construit_le,
    '{{ invocation_id }}'                   as invocation_id,
    '{{ target.name }}'                     as environnement,
    '{{ var("statuts_ca") | join(", ") }}'  as statuts_ca
