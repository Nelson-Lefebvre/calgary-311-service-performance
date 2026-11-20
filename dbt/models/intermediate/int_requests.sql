-- Business flags on every request, including pre-2022 requests still open on 2022-01-01
-- (carryover), which only feed the backlog.
with all_requests as (
    select *, false as is_carryover from {{ ref('stg_requests') }}
    union all
    select *, true as is_carryover from {{ ref('stg_carryover') }}
),

flagged as (
    select
        *,
        trim(split_part(service_name, ' - ', 1)) as service_prefix,
        -- A request with status Open but a closing date was reopened: it is open now.
        case when status_description in ('Open', 'Duplicate (Open)') then null else closed_date end
            as effective_closed_date
    from all_requests
)

select
    f.service_request_id,
    f.requested_date,
    f.updated_date,
    f.closed_date,
    f.effective_closed_date,
    f.status_description,
    f.channel,
    f.service_name,
    f.service_prefix,
    -- Prefixes change when departments are renamed (CBS became DBBS); the seed maps them to stable categories.
    coalesce(m.service_category, 'Other') as service_category,
    coalesce(m.request_type, 'unmapped') as request_type,
    f.agency_responsible,
    coalesce(f.comm_code, 'N/A') as comm_code,
    coalesce(f.comm_name, 'No community') as comm_name,
    f.is_carryover,
    f.status_description = 'Open' and f.closed_date is not null as is_reopened,
    f.status_description in ('Duplicate (Open)', 'Duplicate (Closed)') as is_duplicate,
    f.status_description = 'TO BE DELETED' as is_deleted,
    f.status_description not in ('Duplicate (Open)', 'Duplicate (Closed)', 'TO BE DELETED') as is_valid,
    coalesce(
        f.status_description = 'Closed' and f.closed_date >= f.requested_date, false
    ) as is_closed_valid,
    case
        when f.status_description = 'Closed' and f.closed_date >= f.requested_date
            then date_diff('day', f.requested_date, f.closed_date)
    end as days_to_close
from flagged as f
left join {{ ref('service_category_map') }} as m using (service_prefix)
