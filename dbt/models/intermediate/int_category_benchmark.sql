-- Internal benchmark: P80 of time to close over the benchmark period.
-- Set per service when it has at least 100 closed requests in the period; otherwise the request
-- falls back to its category's P80. Each request is judged against its own service, so a
-- category mixing potholes and snow clearing is not judged on one blended number.
-- Requests from the period still open are left out, which biases the P80 slightly low.
with base as (
    select service_name, service_category, days_to_close
    from {{ ref('int_requests') }}
    where is_closed_valid
        and not is_carryover
        and requested_date >= date '{{ var("benchmark_start") }}'
        and requested_date < date '{{ var("benchmark_end") }}'
)

select
    'service' as benchmark_level,
    service_name as benchmark_key,
    count(*) as benchmark_closed_requests,
    quantile_cont(days_to_close, 0.8) as benchmark_days_p80,
    quantile_cont(days_to_close, 0.9) as benchmark_days_p90
from base
group by service_name
having count(*) >= 100

union all

select
    'category',
    service_category,
    count(*),
    quantile_cont(days_to_close, 0.8),
    quantile_cont(days_to_close, 0.9)
from base
group by service_category
having count(*) >= 100
