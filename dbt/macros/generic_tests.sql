{# Small generic tests so the project needs no dbt packages. #}

{% test at_least(model, column_name, min_value) %}
select * from {{ model }} where {{ column_name }} < {{ min_value }}
{% endtest %}

{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
