-- Singular test: returns rows that violate the unique grain (airport_id, flight_date)
-- in fact_flights. The test passes when zero rows are returned.

select
    airport_id,
    flight_date,
    count(*) as row_count
from {{ ref('fact_flights') }}
group by airport_id, flight_date
having count(*) > 1
