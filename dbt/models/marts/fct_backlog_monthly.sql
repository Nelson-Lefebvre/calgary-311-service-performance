-- Grain: month end x service category x community x age band.
-- Semi-additive: sum across categories or communities, never across months.
-- Includes pre-2022 carryover requests still open at each month end.
-- Excludes "311 Contact Us": 26k contact-form items that were never closed, not open work.
with month_ends as (
    select (date_trunc('month', d) + interval 1 month - interval 1 day)::date as month_end
    from range(date '2022-01-01', date '{{ var("snapshot") }}', interval 1 month) as t(d)
),

complete_month_ends as (
    select month_end from month_ends where month_end < date '{{ var("snapshot") }}'
),

open_at_month_end as (
    select
        m.month_end,
        r.service_category,
        r.request_type,
        r.comm_code,
        r.comm_name,
        date_diff('day', r.requested_date, m.month_end) as age_days
    from complete_month_ends as m
    inner join {{ ref('int_requests') }} as r
        on
            r.requested_date <= m.month_end
            and (r.effective_closed_date is null or r.effective_closed_date > m.month_end)
    where r.is_valid and r.service_name <> '311 Contact Us'
)

select
    month_end,
    service_category,
    request_type,
    comm_code,
    comm_name,
    case
        when age_days <= 7 then '0-7'
        when age_days <= 30 then '8-30'
        when age_days <= 90 then '31-90'
        else '90+'
    end as age_band,
    count(*) as open_requests
from open_at_month_end
group by all
