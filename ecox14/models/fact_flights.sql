{{ config(materialized='table') }}

select
    apt_icao                 as airport_id,
    country_name             as country_id,
    iso_code                 as iso_code,
    flt_date::date           as flight_date,
    year                     as year,
    month_num                as month,
    total_flights            as total_flights,
    flt_dep_1                as departures,
    flt_arr_1                as arrivals,
    total_ifr_flights        as ifr_flights,
    ifr_share                as ifr_share_pct,
    flight_volume_pct_change as flight_pct_change,
    new_cases                as new_cases,
    total_cases              as total_cases,
    new_deaths               as new_deaths,
    total_deaths             as total_deaths,
    stringency_index         as stringency_index,
    flights_per_million_pop  as flights_per_million_pop,
    flights_to_cases_ratio   as flights_to_cases_ratio
from {{ source('silver', 'flights_covid_enriched') }}
where country_name is not null
qualify row_number() over (
    partition by apt_icao, flt_date
    order by flight_volume_pct_change desc
) = 1
