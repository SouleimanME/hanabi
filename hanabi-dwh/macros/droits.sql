{#
    Ouvre l'entrepot en lecture.

    Un schema cree par PostgreSQL n'accorde rien a personne : seul son
    proprietaire peut le traverser. C'est le bon defaut, mais il rend l'entrepot
    invisible a tout ce qui ne se connecte pas avec le role qui l'a construit -
    la console Neon, un client SQL ouvert avec un autre role, un futur service de
    visualisation. Le schema `public` ne pose pas ce probleme parce que
    PostgreSQL lui accorde `USAGE` a tous des sa creation ; les notres non.

    Trois ordres, et pas un de plus :

    - `usage` sur le schema, qui donne le droit de le traverser ;
    - `select` sur les tables existantes ;
    - les memes droits par defaut sur les tables a venir. Sans cette troisieme
      ligne, chaque `dbt run` recreerait les tables gold sans droits, et il
      faudrait rejouer les grants a la main apres chaque construction. C'est
      exactement le genre d'etape manuelle qu'on oublie.

    Aucun droit d'ecriture n'est accorde, a aucun moment. L'entrepot se
    reconstruit, il ne se modifie pas.

    `public` designe ici le pseudo-role « tout le monde », pas le schema du meme
    nom. Sur une base ou plusieurs equipes cohabitent, on nommerait un role de
    lecture dedie ; ici il n'existe qu'un seul role de connexion, et se donner un
    role a soi-meme n'apporterait qu'une indirection.
#}
{% macro accorde_lecture() %}

    {% set couches = ["bronze", "silver", "gold"] %}

    {# `execute` est faux pendant la phase d'analyse, ou dbt rend le Jinja sans
       ouvrir de connexion - c'est ce que fait `dbt parse` en integration
       continue. `run_query` y est deja sans effet, mais la trace, elle,
       s'afficherait quand meme et annoncerait des droits que personne n'a
       accordes. #}
    {% if not execute %}{{ return("") }}{% endif %}

    {% for couche in couches %}
        {% do run_query("grant usage on schema " ~ couche ~ " to public") %}
        {% do run_query("grant select on all tables in schema " ~ couche ~ " to public") %}
        {% do run_query(
            "alter default privileges in schema " ~ couche
            ~ " grant select on tables to public"
        ) %}
    {% endfor %}

    {% do log("Lecture accordee sur " ~ couches | join(", "), info=true) %}

{% endmacro %}
