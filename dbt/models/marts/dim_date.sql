WITH dates AS (
    SELECT DISTINCT CAST(event_ts AS DATE) AS date_day FROM {{ ref('stg_events') }}
    UNION
    SELECT DISTINCT CAST(event_ts AS DATE) AS date_day FROM {{ ref('stg_prices') }}
)
SELECT
    CAST(strftime(date_day, '%Y%m%d') AS INTEGER) AS date_sk,
    date_day,
    EXTRACT(year FROM date_day) AS year,
    EXTRACT(month FROM date_day) AS month,
    EXTRACT(day FROM date_day) AS day,
    EXTRACT(dow FROM date_day) AS day_of_week,
    strftime(date_day, '%A') AS day_name,
    CASE WHEN EXTRACT(dow FROM date_day) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM dates
