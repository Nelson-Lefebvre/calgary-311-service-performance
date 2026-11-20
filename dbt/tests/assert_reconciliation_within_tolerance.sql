-- Level 2 cross-check against the separate arf6-qysm extract.
-- Only 2024 is comparable: from 2025 the extract hits its 1M-row cap and whole months go
-- missing (documented in docs/data_quality.md). In 2024 the second extract runs 0.2-1.1% short.
select *
from {{ ref('reconciliation_monthly') }}
where request_month < date '2025-01-01'
    and abs(diff_pct) > 1.5
