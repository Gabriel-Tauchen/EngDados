import streamlit as st
import queries

# Page configuration
st.set_page_config(
    page_title="European Aviation & COVID-19 Observatory",
    page_icon="✈️",
    layout="wide",
)

# Header
st.title("✈️ European Air Traffic & COVID-19 Observatory")
st.markdown(
    "Analytical observatory consuming the **Gold dimensional layer** from DuckDB (`project.duckdb`). "
    "Designed following declarative engineering principles: the UI is strictly a read-only consumer."
)

# =============================================================================
# SIDEBAR FILTERS (Organized by which dashboards and sections they control)
# =============================================================================
st.sidebar.title("🎛️ Dashboard Filters")
st.sidebar.markdown(
    "Use the controls below to filter different analytical sections across the observatory."
)

# --- Group A: Regional & Annual Scope ---
st.sidebar.subheader("🌐 Global Macro Filters")
st.sidebar.caption("👉 Controls: **Headline KPIs**, **Regional Distribution Chart**, and **Top Airports Table**")

available_years = queries.get_available_years()
selected_year = st.sidebar.selectbox("Reference Year", available_years, index=0)

available_regions = ["All"] + queries.get_available_regions()
selected_region = st.sidebar.selectbox("Geographic Region", available_regions, index=0)

st.sidebar.divider()

# --- Group B: Country Scope ---
st.sidebar.subheader("🎯 Country Deep-Dive Filter")
st.sidebar.caption("👉 Controls: **Multi-Index Comparative Overlay** and **Historical Flight Evolution**")

available_countries = queries.get_available_countries(
    region=None if selected_region == "All" else selected_region
)
country_options = ["All Countries (Aggregated)"] + available_countries
selected_country = st.sidebar.selectbox(
    "Country Scope",
    country_options,
    index=0,  # Default to "All Countries (Aggregated)"
    help="Select 'All Countries (Aggregated)' to combine Europe-wide data, or pick a specific country for localized analysis.",
)

# =============================================================================
# SECTION 1: Headline KPIs (Affected by selected_region and selected_year)
# =============================================================================
st.markdown(f"#### 📌 Macro Overview — Region: `{selected_region}` | Year: `{selected_year}`")
metrics = queries.get_summary_metrics(region=selected_region, year=selected_year)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric(
        label="Total Flights",
        value=f"{metrics['total_flights']:,}",
        help="Aggregated operations (departures + arrivals) across selected region and year",
    )
with kpi2:
    st.metric(
        label="Reported COVID-19 Cases",
        value=f"{metrics['total_new_cases']:,}",
        help="Sum of new COVID-19 cases in the selected period",
    )
with kpi3:
    st.metric(
        label="Avg Government Stringency",
        value=f"{metrics['avg_stringency']:.1f} / 100",
        help="Mean government stringency policy index (0 = none, 100 = full lockdown)",
    )
with kpi4:
    st.metric(
        label="Monitored Countries",
        value=str(metrics["country_count"]),
        help="Number of distinct nations represented in this slice",
    )

st.divider()

# =============================================================================
# SECTION 2: Multi-Index Temporal Overlay (Affected by selected_country & sidebar)
# =============================================================================
st.subheader(f"📈 Comparative Impact Overlay: {selected_country}")
st.markdown(
    "Superimpose government restrictions, flight operations, and COVID-19 infection waves over time. "
    "Toggle any of the three indices to analyze their interdependencies and verify how sanitary measures impacted aviation."
)

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])
with ctrl_col1:
    overlay_granularity = st.selectbox(
        "Granularity",
        options=["Monthly", "Yearly"],
        index=0,
        help="Monthly reflects granular lockdown waves; Yearly provides high-level macro trajectories.",
    )
with ctrl_col2:
    overlay_scale = st.radio(
        "Scale Representation",
        options=["Normalized (0-100%)", "Absolute Values"],
        index=0,
        help="Normalized scales all series between 0% and 100% of their peak so curves with distinct units can be compared side-by-side.",
    )
with ctrl_col3:
    year_range = st.slider(
        "Analysis Period",
        min_value=2019,
        max_value=2024,
        value=(2020, 2023),
        help="Time window. Detailed pandemic metrics (stringency and cases) are concentrated between 2020 and 2023.",
    )

# Toggles for the three series
tog_col1, tog_col2, tog_col3 = st.columns(3)
with tog_col1:
    show_flights = st.toggle("✈️ Total Flights", value=True)
with tog_col2:
    show_stringency = st.toggle("🛡️ Government Stringency Index", value=True)
with tog_col3:
    show_cases = st.toggle("🦠 COVID-19 New Cases", value=True)

timeline_df = queries.get_multivariate_timeline(
    country_name=selected_country,
    granularity="month" if overlay_granularity == "Monthly" else "year",
    start_year=year_range[0],
    end_year=year_range[1],
    region=selected_region,
)

if timeline_df.empty:
    st.info(f"No temporal data available for {selected_country} within {year_range[0]}-{year_range[1]}.")
elif not (show_flights or show_stringency or show_cases):
    st.warning("⚠️ All three indices are toggled off. Please enable at least one index toggle above to display the chart.")
else:
    # Prepare mapping of active series and fixed distinctive color palette
    # User requirement: COVID-19 curve MUST be green!
    column_mapping = {}
    active_labels = []
    active_colors = []

    if show_flights:
        label = "Flights (Volume)" if overlay_scale == "Absolute Values" else "Flights (% of Peak)"
        column_mapping["total_flights"] = label
        active_labels.append(label)
        active_colors.append("#1f77b4")  # Classic Aviation Blue

    if show_stringency:
        label = "Stringency Index (0-100)"
        column_mapping["avg_stringency"] = label
        active_labels.append(label)
        active_colors.append("#ef4444")  # Alert Red

    if show_cases:
        label = "COVID-19 Cases (Count)" if overlay_scale == "Absolute Values" else "COVID-19 Cases (% of Peak)"
        column_mapping["new_cases"] = label
        active_labels.append(label)
        active_colors.append("#10b981")  # Vibrant Green (requested by user)

    if overlay_scale == "Normalized (0-100%)":
        chart_data = queries.normalize_series_min_max(timeline_df, list(column_mapping.keys()))
    else:
        chart_data = timeline_df.copy()

    # Rename active columns and render multi-line chart
    chart_data = chart_data.rename(columns=column_mapping)
    chart_cols = ["period"] + active_labels

    st.line_chart(
        chart_data[chart_cols],
        x="period",
        y=active_labels,
        color=active_colors,
        height=390,
    )

    with st.expander("🔍 View Raw Numerical Data"):
        raw_display = timeline_df[["period", "total_flights", "avg_stringency", "new_cases"]].copy()
        raw_display.columns = ["Period", "Total Flights", "Stringency Index (0-100)", "New COVID Cases"]
        st.dataframe(raw_display, hide_index=True, use_container_width=True)

st.divider()

# =============================================================================
# SECTION 3: Regional Flight Distribution & Indicators Table (Affected by selected_region & selected_year)
# =============================================================================
indicators_df = queries.get_indicators_by_region_and_year(
    region=selected_region, year=selected_year
)

col_chart, col_table = st.columns([3, 2])

with col_chart:
    st.subheader(f"Top Flight Volumes — {selected_region} ({selected_year})")
    if not indicators_df.empty:
        top_countries = indicators_df.head(10)
        st.bar_chart(
            top_countries,
            x="country_name",
            y="total_flights",
            color="#1f77b4",
            height=360,
        )
    else:
        st.info("No records matching the selected filter criteria.")

with col_table:
    st.subheader(f"Country Indicators Table ({selected_year})")
    if not indicators_df.empty:
        display_df = indicators_df[[
            "country_name", "total_flights", "pct_change", "region_share_pct", "new_cases"
        ]].copy()
        display_df.columns = [
            "Country", "Total Flights", "YoY Change (%)", "Regional Share (%)", "COVID Cases"
        ]
        st.dataframe(
            display_df,
            hide_index=True,
            height=360,
            use_container_width=True,
        )
    else:
        st.info("No records to display.")

st.divider()

# =============================================================================
# SECTION 4: Historical Evolution & Top Airports
# =============================================================================
sec_trend, sec_airports = st.columns([1, 1])

with sec_trend:
    st.subheader(f"Historical Flight Trend: {selected_country} (2019-2024)")
    trend_df = queries.get_flight_trend_by_country(selected_country)
    if not trend_df.empty:
        st.line_chart(
            trend_df,
            x="year",
            y="total_flights",
            color="#1f77b4",
            height=300,
        )
    else:
        st.info(f"No historical trend available for {selected_country}.")

with sec_airports:
    st.subheader(f"Top 10 Operational Airports ({selected_year})")
    top_airports_df = queries.get_top_airports(year=selected_year, limit=10)
    if not top_airports_df.empty:
        airports_display = top_airports_df[[
            "airport_name", "country_id", "total_flights", "avg_ifr_share_pct"
        ]].copy()
        airports_display.columns = ["Airport", "Country", "Total Flights", "IFR Share (%)"]
        st.dataframe(
            airports_display,
            hide_index=True,
            height=300,
            use_container_width=True,
        )
    else:
        st.info(f"No airport traffic recorded for year {selected_year}.")

# =============================================================================
# FOOTER: Provenance & Data Lineage
# =============================================================================
st.divider()
total_records = len(indicators_df)
st.caption(
    f"📊 **Data Lineage & Governance:** Source data from **Eurocontrol (Air Traffic Europe)** and "
    f"**Our World in Data (COVID-19 Pandemic Dataset)**. Total rows in current view: {total_records}. "
    f"Connected to in-process DuckDB analytical warehouse (`project.duckdb`) in strict read-only mode."
)
