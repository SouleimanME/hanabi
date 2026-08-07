{#
    Nom de schema d'un modele.

    dbt prefixe par defaut le schema personnalise par celui du profil : un
    modele declare `+schema: gold` atterrit dans `public_gold`. Le comportement
    a du sens quand plusieurs personnes construisent le meme projet dans une
    base partagee, chacune dans son prefixe. Ici, il n'y a qu'un entrepot, lu
    par une API qui doit connaitre le nom du schema a l'avance : on veut
    `bronze`, `silver` et `gold`, tels qu'ecrits.

    Sans schema personnalise (cas qui ne se presente pas dans ce projet), on
    retombe sur celui du profil.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}


{#
    Liste SQL des statuts qui comptent comme du chiffre d'affaires.

    Ecrite une fois plutot que recopiee dans la dizaine de modeles qui filtrent
    dessus : le jour ou un statut s'ajoute, il s'ajoute ici.
#}
{% macro statuts_ca() -%}
    ({%- for statut in var('statuts_ca') -%}
        '{{ statut }}'{{ ", " if not loop.last }}
    {%- endfor -%})
{%- endmacro %}
