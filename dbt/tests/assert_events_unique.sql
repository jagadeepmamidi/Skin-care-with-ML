SELECT event_id, COUNT(*) AS n
FROM {{ ref('stg_events') }}
GROUP BY 1
HAVING COUNT(*) > 1
