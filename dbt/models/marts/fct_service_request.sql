-- Grain: one valid request from 2022 onward.
with benchmarks as (
    select
        r.service_request_id,
        coalesce(s.benchmark_days_p80, c.benchmark_days_p80) as benchmark_days_p80,
        coalesce(s.benchmark_days_p90, c.benchmark_days_p90) as benchmark_days_p90,
        case
            when s.benchmark_days_p80 is not null then 'service'
            when c.benchmark_days_p80 is not null then 'category'
        end as benchmark_level
    from {{ ref('int_requests') }} as r
    left join {{ ref('int_category_benchmark') }} as s
        on s.benchmark_level = 'service' and r.service_name = s.benchmark_key
    left join {{ ref('int_category_benchmark') }} as c
        on c.benchmark_level = 'category' and r.service_category = c.benchmark_key
)

select
    r.service_request_id,
    r.requested_date,
    r.effective_closed_date as closed_date,
    r.status_description,
    r.channel,
    r.service_name,
    r.service_category,
    r.request_type,
    r.agency_responsible,
    r.comm_code,
    r.comm_name,
    r.is_reopened,
    r.is_closed_valid,
    r.days_to_close,
    b.benchmark_days_p80,
    b.benchmark_days_p90,
    b.benchmark_level,
    case
        when r.is_closed_valid and b.benchmark_days_p80 is not null
            then r.days_to_close <= b.benchmark_days_p80
    end as is_within_benchmark,
    case
        when r.is_closed_valid and b.benchmark_days_p90 is not null
            then r.days_to_close <= b.benchmark_days_p90
    end as is_within_benchmark_p90,
    r.requested_date >= date '{{ var("benchmark_end") }}' as is_assessed_period
from {{ ref('int_requests') }} as r
left join benchmarks as b using (service_request_id)
where r.is_valid and not r.is_carryover
