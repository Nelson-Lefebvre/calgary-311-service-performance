-- One row per 311 request in the snapshot. Types only; business rules live downstream.
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
from {{ source('raw', 'requests') }}
