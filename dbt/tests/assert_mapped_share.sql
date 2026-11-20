-- Plausibility: the category seed must cover at least 97% of valid requests,
-- so the "Other" bucket stays small enough to ignore in the dashboard.
select share_mapped
from (
    select avg(case when service_category <> 'Other' then 1.0 else 0 end) as share_mapped
    from {{ ref('fct_service_request') }}
)
where share_mapped < 0.97
