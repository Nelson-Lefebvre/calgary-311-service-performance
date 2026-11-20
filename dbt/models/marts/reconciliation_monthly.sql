-- Monthly totals from iahh-g8bj against the separate arf6-qysm extract (2024+, capped at 1M rows).
with main as (
    select
        date_trunc('month', requested_date)::date as request_month,
        count(*) as main_requests
    from {{ ref('stg_requests') }}
    where requested_date >= date '2024-01-01'
    group by 1
),

second as (
    select
        date_trunc('month', requested_date)::date as request_month,
        count(*) as second_requests
    from {{ ref('stg_second_extract') }}
    group by 1
)

select
    request_month,
    coalesce(main.main_requests, 0) as main_requests,
    coalesce(second.second_requests, 0) as second_requests,
    coalesce(second.second_requests, 0) - coalesce(main.main_requests, 0) as diff,
    round(
        100.0 * (coalesce(second.second_requests, 0) - coalesce(main.main_requests, 0))
        / nullif(main.main_requests, 0),
        3
    ) as diff_pct
from main
full outer join second using (request_month)
order by request_month
