-- Singular test: returns rows that violate the unique grain (country_id, year)
-- in fact_indicator. The test passes when zero rows are returned.

select
    country_id,
    year,
    count(*) as row_count
from {{ ref('fact_indicator') }}
group by country_id, year
having count(*) > 1
