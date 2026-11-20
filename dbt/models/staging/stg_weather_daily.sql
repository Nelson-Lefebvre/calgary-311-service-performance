select
    cast(left("LOCAL_DATE", 10) as date) as weather_date,
    cast("MIN_TEMPERATURE" as double) as min_temp_c,
    cast("MAX_TEMPERATURE" as double) as max_temp_c,
    cast("MEAN_TEMPERATURE" as double) as mean_temp_c,
    cast("TOTAL_SNOW" as double) as snowfall_cm,
    cast("SNOW_ON_GROUND" as double) as snow_on_ground_cm,
    cast("TOTAL_PRECIPITATION" as double) as precipitation_mm
from {{ source('raw', 'weather_daily') }}
