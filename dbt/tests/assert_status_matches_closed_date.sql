-- Internal consistency: a closed request has a closing date on or after its request date.
-- Open requests with a closing date (reopened) are handled by effective_closed_date and
-- counted in docs/data_quality.md, so they are not violations here.
select service_request_id, status_description, requested_date, closed_date
from {{ ref('int_requests') }}
where not is_carryover
    and status_description = 'Closed'
    and (closed_date is null or closed_date < requested_date)
