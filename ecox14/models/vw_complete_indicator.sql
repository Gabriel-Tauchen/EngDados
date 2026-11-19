{{ config(materialized='view') }}

select
    f.*,
    d.country_name,
    d.region,
    d.population
from {{ ref('fact_indicator') }} f
join {{ ref('dim_country') }} d using (country_id)
