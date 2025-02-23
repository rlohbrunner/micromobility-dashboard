import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from shapely.geometry import LineString 
import branca.colormap as cm
import random
import streamlit as st
from streamlit_folium import folium_static
import os
from scipy.stats import percentileofscore 

from functions2 import (
    filter_top_1_percent, 
    merge_connected_segments, 
    plot_linestrings, 
    summary_statistics,
    plot_trip_count_histogram,
    plot_trip_count_histogram_flipped
)

# STREAMLIT UI
st.title("Atlanta 2024 Scooter Route Analysis")
st.sidebar.header("Filters")

# Define the local data path
DATA_DIR = "data/"

QUARTER_FILES = {
    "Q1": os.path.join(DATA_DIR, "routes_Q1.geojson"),
    "Q2": os.path.join(DATA_DIR, "routes_Q2.geojson"),
    "Q3": os.path.join(DATA_DIR, "routes_Q3.geojson"),
    "Q4": os.path.join(DATA_DIR, "routes_Q4.geojson"),
}

# Load data from local file system
@st.cache_data
def load_geojson(file_path):
    return gpd.read_file(file_path)

# Initialize session state variables if they don't exist
if "gdf" not in st.session_state:
    st.session_state.gdf = load_geojson(QUARTER_FILES["Q3"])  # Default quarter
if "selected_quarter" not in st.session_state:
    st.session_state.selected_quarter = "Q3"
if "min_trip_count" not in st.session_state:
    st.session_state.min_trip_count = 4500
if "filter_applied" not in st.session_state:
    st.session_state.filter_applied = False  

# Sidebar input: Quarter selection
selected_quarter = st.sidebar.selectbox(
    "Select a 2024 Quarter:", list(QUARTER_FILES.keys()), index=list(QUARTER_FILES.keys()).index(st.session_state.selected_quarter)
)

# Load the new dataset only if the quarter selection changes
if selected_quarter != st.session_state.selected_quarter:
    st.session_state.gdf = load_geojson(QUARTER_FILES[selected_quarter])
    st.session_state.selected_quarter = selected_quarter
    st.session_state.filter_applied = False  # Reset filter flag

# Get max trip count dynamically based on the selected quarter
max_trip_count = int(st.session_state.gdf['count'].max()) if 'count' in st.session_state.gdf.columns else 50

# Sidebar input: Min trip count selection
min_trip_count = st.sidebar.number_input(
    "Filter to only show routes with at least X scooter trips passing through them during the quarter:", 
    min_value=0, 
    max_value=max_trip_count, 
    value=min(4500, max_trip_count),  
    step=1
)

# Apply Filter button logic
if st.sidebar.button("Apply Filter"):
    st.session_state.filter_applied = True  
    st.session_state.min_trip_count = min_trip_count
    st.session_state.gdf = load_geojson(QUARTER_FILES[selected_quarter])  # Reload data
    st.session_state.gdf = st.session_state.gdf[st.session_state.gdf['count'] >= min_trip_count]  # Apply filter

# Display content based on filter state
if not st.session_state.filter_applied:
    st.subheader("About this web app")
    st.write(
        "Welcome to Ryan Lohbrunner's **Micromobility Data Analysis** web app! 🛴📊\n\n"
        "Use the filters in the sidebar to select a quarter and specify a minimum trip count. "
        "A few seconds (~5-20) after applying the filter, an interactive map will pop up and display the scooter routes "
        "in the city, along with key statistics. This web app is currently under development and will include new "
        "features, cities, time periods, vehicle types, and data tools within the upcoming weeks. "
        "Data ~~stolen~~ scraped from Ride Report, found at public.ridereport.com."
    )
else:
    st.subheader("Routes")
    map_output = plot_linestrings(st.session_state.gdf)
    folium_static(map_output)
    # Display Histograms
    plot_trip_count_histogram(st.session_state.gdf)
    plot_trip_count_histogram_flipped(st.session_state.gdf)
    # Display summary statistics
    summary_statistics(st.session_state.gdf)

