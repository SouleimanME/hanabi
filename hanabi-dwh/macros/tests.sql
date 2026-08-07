{#
    Deux tests generiques que dbt ne fournit pas en standard.

    Ils existent tous les deux dans le paquet `dbt_utils`, sous les noms
    `accepted_range` et `unique_combination_of_columns`. Les reecrire en une
    quinzaine de lignes evite d'ajouter une dependance - et son telechargement,
    et sa version a suivre - pour deux requetes que l'on lit d'un coup d'oeil.
    Le jour ou il en faudrait dix, le paquet redeviendrait le bon choix.

    Un test dbt rend les lignes fautives : il passe quand il ne rend rien.
#}

{#
    Valeur comprise entre deux bornes, incluses.

    Les NULL sont ignores : `not_null` est un test separe, et le confondre avec
    celui-ci rendrait illisible le message d'echec.
#}
{% test intervalle(model, column_name, mini, maxi) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ mini }} or {{ column_name }} > {{ maxi }})

{% endtest %}


{#
    Unicite d'une combinaison de colonnes.

    Le test `unique` de dbt ne porte que sur une colonne. Or la clef d'une table
    d'agregats est presque toujours composee - (cohorte, decalage), (produit A,
    produit B) - et c'est justement la que le doublon se glisse, quand une
    jointure duplique des lignes sans qu'aucun total ne paraisse aberrant.
#}
{% test combinaison_unique(model, colonnes) %}

select
    {{ colonnes | join(", ") }},
    count(*) as occurrences
from {{ model }}
group by {{ colonnes | join(", ") }}
having count(*) > 1

{% endtest %}
