-- Grain: day x service category, with that day's weather at Calgary International Airport.
select
    r.requested_date as request_date,
    r.service_category,
    count(*) as requests,
    any_value(w.snowfall_cm) as snowfall_cm,
    any_value(w.snow_on_ground_cm) as snow_on_ground_cm,
    any_value(w.min_temp_c) as min_temp_c,
    any_value(w.precipitation_mm) as precipitation_mm
from {{ ref('fct_service_request') }} as r
left join {{ ref('stg_weather_daily') }} as w on r.requested_date = w.weather_date
group by all
