SELECT DISTINCT
    md5(event_type) AS event_type_sk,
    event_type
FROM {{ ref('stg_events') }}
