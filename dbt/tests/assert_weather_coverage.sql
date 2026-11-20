-- Plausibility: every request day in the period has a weather row.
{{ config(severity='warn') }}

select distinct r.request_date
from {{ ref('fct_daily_weather_requests') }} as r
where r.snowfall_cm is null and r.min_temp_c is null
