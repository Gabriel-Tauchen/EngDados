{{ config(materialized='table') }}

select
    country_name                      as country_id,
    iso_code                          as iso_code,
    country_name                      as country_name,
    arg_max(continent, date)          as continent,
    arg_max(continent, date)          as region,
    arg_max(population, date)::bigint as population
from {{ source('silver', 'covid19') }}
where country_name is not null
group by country_name, iso_code
