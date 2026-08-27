-- Custom generic tests without dbt_utils.
{% test non_negative(model, column_name) %}
SELECT *
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} < 0
{% endtest %}
