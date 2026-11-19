{{ config(materialized='table') }}

select
    apt_icao                      as airport_id,
    arg_max(apt_name, flt_date)   as airport_name,
    country_name                  as country,
    arg_max(state_name, flt_date) as state_name
from {{ source('silver', 'air_traffic_eu') }}
group by apt_icao, country_name
