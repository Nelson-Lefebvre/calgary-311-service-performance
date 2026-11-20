-- Grain: month end x request type x service category x service name x community x age band.
-- Last 13 complete month ends only (operational view); fct_backlog_monthly keeps the full history.
-- open_3m_earlier: same grain three month ends earlier, 0 when nothing was open then,
-- so rows that appear or disappear between the two dates are kept.
-- Same exclusions as fct_backlog_monthly. Semi-additive: never sum across months.
with month_ends as (
    select (date_trunc('month', d) + interval 1 month - interval 1 day)::date as month_end
    from range(date '2022-01-01', date '{{ var("snapshot") }}', interval 1 month) as t(d)
),

-- 13 shown plus 3 for the look-back
window_month_ends as (
    select month_end from month_ends
    where month_end < date '{{ var("snapshot") }}'
    order by month_end desc
    limit 16
),

shown_month_ends as (
    select month_end from window_month_ends order by month_end desc limit 13
),

open_counts as (
    select
        m.month_end,
        r.request_type,
        r.service_category,
        r.service_name,
        r.comm_code,
        r.comm_name,
        case
            when date_diff('day', r.requested_date, m.month_end) <= 7 then '0-7'
            when date_diff('day', r.requested_date, m.month_end) <= 30 then '8-30'
            when date_diff('day', r.requested_date, m.month_end) <= 90 then '31-90'
            else '90+'
        end as age_band,
        count(*) as open_requests
    from window_month_ends as m
    inner join {{ ref('int_requests') }} as r
        on
            r.requested_date <= m.month_end
            and (r.effective_closed_date is null or r.effective_closed_date > m.month_end)
    where r.is_valid and r.service_name <> '311 Contact Us'
    group by all
),

three_months_later as (
    select
        last_day(month_end + interval 3 month) as month_end,
        request_type, service_category, service_name, comm_code, comm_name, age_band,
        open_requests as open_3m_earlier
    from open_counts
),

joined as (
    select
        month_end, request_type, service_category, service_name, comm_code, comm_name, age_band,
        coalesce(c.open_requests, 0) as open_requests,
        coalesce(p.open_3m_earlier, 0) as open_3m_earlier
    from open_counts as c
    full join three_months_later as p
        using (month_end, request_type, service_category, service_name, comm_code, comm_name, age_band)
)

select
    j.*,
    -- 2019 census. Null below 1,000 residents: new areas had a handful of people in 2019 and
    -- would top any per-1,000 ranking. Joined on name: the census reuses 4 codes (WBN, OGD, PKD, SIL)
    -- for communities the 311 data codes differently (TAR, OAK, PKL, SRI); names are unique.
    case when pop.population_2019 >= 1000 then pop.population_2019 end as population_2019
from joined as j
left join {{ ref('stg_community_population') }} as pop
    on j.comm_name = pop.comm_name
where j.month_end in (select month_end from shown_month_ends)
