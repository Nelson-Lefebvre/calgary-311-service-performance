-- Grain: service category x month of request. Ratios recomputed from counts at this grain;
-- each request was judged against its own service benchmark.
select
    service_category,
    any_value(request_type) as request_type,
    date_trunc('month', requested_date)::date as request_month,
    count(*) as requests,
    count(*) filter (where is_closed_valid) as closed_requests,
    median(days_to_close) as median_days_to_close,
    quantile_cont(days_to_close, 0.9) as p90_days_to_close,
    count(*) filter (where is_within_benchmark) as closed_within_benchmark,
    count(*) filter (where is_within_benchmark is not null) as closed_with_benchmark,
    count(*) filter (where is_within_benchmark)
        / nullif(count(*) filter (where is_within_benchmark is not null), 0) as pct_within_benchmark,
    count(*) filter (where is_within_benchmark_p90)
        / nullif(count(*) filter (where is_within_benchmark_p90 is not null), 0)
        as pct_within_benchmark_p90
from {{ ref('fct_service_request') }}
group by service_category, date_trunc('month', requested_date)::date
