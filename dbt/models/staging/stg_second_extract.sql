select
    service_request_id,
    cast(left(requested_date, 10) as date) as requested_date,
    cast(left(closed_date, 10) as date) as closed_date,
    status_description
from {{ source('raw', 'second_extract') }}
