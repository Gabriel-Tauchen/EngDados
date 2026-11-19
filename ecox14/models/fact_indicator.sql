{{ config(materialized='table') }}

with aggregates as (
    select
        country_name                        as country_id,
        year                                as year,
        sum(total_flights)::bigint          as value,
        sum(total_flights)::bigint          as total_flights,
        sum(total_ifr_flights)::double      as total_ifr_flights,
        coalesce(sum(new_cases), 0)::double as new_cases,
        coalesce(max(total_cases), 0)::bigint as total_cases,
        coalesce(sum(new_deaths), 0)::double  as new_deaths,
        coalesce(max(total_deaths), 0)::bigint as total_deaths,
        round(coalesce(avg(stringency_index), 0), 2) as avg_stringency_index
    from {{ source('silver', 'flights_covid_enriched') }}
    where country_name is not null
    group by country_name, year
),
with_derivatives as (
    select
        country_id,
        year,
        value,
        total_flights,
        total_ifr_flights,
        new_cases,
        total_cases,
        new_deaths,
        total_deaths,
        avg_stringency_index,
        round(
            (value - lag(value) over (partition by country_id order by year)) * 100.0 /
            nullif(lag(value) over (partition by country_id order by year), 0),
            2
        ) as pct_change,
        round(
            value * 100.0 / sum(value) over (partition by year),
            2
        ) as region_share_pct
    from aggregates
)
select * from with_derivatives
