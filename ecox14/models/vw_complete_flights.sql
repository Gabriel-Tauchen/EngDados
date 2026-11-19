{{ config(materialized='view') }}

select
    f.*,
    a.airport_name,
    a.state_name,
    d.continent,
    d.population
from {{ ref('fact_flights') }} f
join {{ ref('dim_airport') }} a using (airport_id)
join {{ ref('dim_country') }} d using (country_id)
