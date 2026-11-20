-- Last municipal census is 2019; keep only that year.
-- The source reuses 4 codes for two communities each (WBN, OGD, PKD, SIL), so the key is code + name.
select
    comm_code,
    upper(trim(name)) as comm_name,
    cast(population as integer) as population_2019
from {{ source('raw', 'community_population') }}
where census_year = '2019'
