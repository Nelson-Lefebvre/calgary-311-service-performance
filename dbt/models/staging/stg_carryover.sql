-- Pre-2022 requests still open on 2022-01-01. Same columns as stg_requests.
select
    service_request_id,
    cast(left(requested_date, 10) as date) as requested_date,
    cast(left(updated_date, 10) as date) as updated_date,
    cast(left(closed_date, 10) as date) as closed_date,
    status_description,
    source as channel,
    trim(service_name) as service_name,
    trim(agency_responsible) as agency_responsible,
    nullif(trim(comm_code), '') as comm_code,
    nullif(trim(comm_name), '') as comm_name,
    location_type
from {{ source('raw', 'carryover') }}
