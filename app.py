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

# FUNCTIONS
def filter_top_1_percent(gdf):
    """
    Filters the GeoDataFrame to keep only the top 1% of routes based on 'count'.
    
    Parameters:
        gdf (GeoDataFrame): Original dataset containing 'count' and 'geometry'.
    
    Returns:
        top_1_gdf (GeoDataFrame): Filtered dataset with only the top 1% of routes.
    """
    # Fills in N/A values ("< 100")
    gdf['count'] = gdf['count'].fillna(0)
    # Compute the 99th percentile threshold
    threshold = np.percentile(gdf['count'], 99)
    # Filter the GeoDataFrame
    top_1_gdf = gdf[gdf['count'] >= threshold].copy()
    return top_1_gdf

def merge_connected_segments(gdf):
    """
    Merges connected line segments into longer "super segments."
    
    Parameters:
        gdf (GeoDataFrame): Contains 'geometry' with LINESTRINGs.
    
    Returns:
        merged_gdf (GeoDataFrame): GeoDataFrame with merged "super segments."
    """
    def round_coords(coord):
        """Round a coordinate tuple (lon, lat) to 3 decimal places."""
        return (round(coord[0], 3), round(coord[1], 3))
    # Extract first and last coordinates (rounded to 3 decimal places)
    gdf['first_coord'] = gdf['geometry'].apply(lambda x: round_coords(x.coords[0]))
    gdf['last_coord'] = gdf['geometry'].apply(lambda x: round_coords(x.coords[-1]))
    # Dictionary to store sequences of connected segments
    segment_groups = []
    # Keep track of visited segments
    visited = set()
    # Function to recursively merge connected segments
    def build_super_segment(segment_idx, current_coords):
        if segment_idx in visited:
            return
        visited.add(segment_idx)
        # Append current segment coordinates
        current_coords.extend(list(gdf.loc[segment_idx, 'geometry'].coords)[1:])  # Avoid duplicate start points
        # Find next segment
        next_segments = gdf[gdf['first_coord'] == gdf.loc[segment_idx, 'last_coord']].index.tolist()
        for next_idx in next_segments:
            build_super_segment(next_idx, current_coords)
    # Iterate through all segments to form super segments
    for idx in gdf.index:
        if idx not in visited:
            super_segment_coords = list(gdf.loc[idx, 'geometry'].coords)
            build_super_segment(idx, super_segment_coords)
            segment_groups.append(LineString(super_segment_coords))
    # Create a new GeoDataFrame with merged "super segments"
    merged_gdf = gpd.GeoDataFrame(geometry=segment_groups, crs=gdf.crs, )
    return merged_gdf

def plot_linestrings(gdf):
    """
    Creates a Ride Report-style map with:
    - A step colormap based on quartiles of the trip count data.
    - A light grey basemap for better contrast.
    - Scaled line widths based on percentage.
    - A color legend displaying actual min/max trip counts while mapping log-transformed colors.
    
    Parameters:
        gdf (GeoDataFrame): Contains 'count' and 'percentage' fields.
    
    Returns:
        folium.Map: Interactive map styled like Ride Report.
    """
    # Ensure CRS is WGS84
    gdf = gdf.to_crs(epsg=4326)
    # Convert to projected CRS for accurate centroid calculation
    projected_gdf = gdf.to_crs(epsg=32616)
    center_lat = projected_gdf.geometry.centroid.to_crs(epsg=4326).y.median()
    center_lon = projected_gdf.geometry.centroid.to_crs(epsg=4326).x.median()
    # Initialize Folium map with light basemap
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB Positron")
    
    # Checks for counts
    if 'count' in gdf.columns:
        # Handle missing values in 'count' and 'percentage'
        gdf['count'] = gdf['count'].fillna(50)  # Avoid log(0)
        gdf['percentage'] = gdf['percentage'].fillna(0.001)  # Default to small width

        # Compute percentile ranking for each count value
        gdf['percentile'] = gdf['count'].apply(lambda x: percentileofscore(gdf['count'], x))

        # Compute quartile breaks for Step Colormap
        quantiles = np.percentile(gdf['count'], [0, 30, 50, 70, 90])
        
        color_steps = ['#53bf7f', '#a2d9ce', '#85c1e9', '#bd8cd2', '#572a6a']
        # Define StepColormap based on quantiles
        colormap = cm.StepColormap(
            colors=color_steps,
            index=quantiles.tolist(),  # Ensure step values match percentiles
            vmin=quantiles[0], vmax=quantiles[-1]
        )

        # Normalize percentage for line width scaling
        min_percentage, max_percentage = gdf['percentage'].min(), gdf['percentage'].max()

        def scale_width(value, min_val, max_val):
            """Scales line width between 1 and 5 based on percentage."""
            return 6 + 2 * ((value - min_val) / (max_val - min_val) if max_val > min_val else 1)

        # Add line geometries to the map with colors & widths
        for _, row in gdf.iterrows():
            if row.geometry.geom_type == 'LineString':
                coords = [(point[1], point[0]) for point in row.geometry.coords]  # folium uses (lat, lon)
                color = colormap(row['count'])  # ✅ Step colormap applied
                width = scale_width(row['percentage'], min_percentage, max_percentage)  # Scale width

                # 🏆 Format tooltip: round percentage & percentile
                tooltip_text = (
                    f"Count of Trips Passing Through This Segment: {row['count']}<br>"
                    f"Percent of Total Period Trips: {row['percentage']:.2f}%<br>"
                    f"Count Percentile in Comparison to Other Segments: {row['percentile']:.2f}%"
                )

                folium.PolyLine(coords, color=color, weight=width, opacity=0.8, 
                                tooltip=tooltip_text).add_to(m)

        # Fix colormap legend to show quartile step values
        #colormap.caption = "Trip Density"
        #colormap.add_to(m)
    else:
        # Use random colors for each segment
        random.seed(42)
        colors = [f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}' for _ in range(len(gdf))]

        # Add line geometries to the map
        for i, (row, color) in enumerate(zip(gdf.iterrows(), colors)):
            row = row[1]  # Extract row data
            coords = [(point[1], point[0]) for point in row.geometry.coords]  # folium uses (lat, lon)
            folium.PolyLine(
                coords, color=color, weight=5, opacity=0.8, 
                tooltip=f"Segment {i}"
            ).add_to(m)

    return m

def summary_statistics(gdf):
    """
    Computes and displays summary statistics for the GeoDataFrame.

    Parameters:
        gdf (GeoDataFrame): Contains 'count' and 'geometry' fields.
    """
    # Compute total number of routes
    total_routes = len(gdf)

    # Compute trip count statistics if 'count' exists
    if 'count' in gdf.columns:
        min_count = gdf['count'].min()
        q1_count = gdf['count'].quantile(0.25)  # 1st quartile (25th percentile)
        median_count = gdf['count'].median()  # 2nd quartile (50th percentile)
        q3_count = gdf['count'].quantile(0.75)  # 3rd quartile (75th percentile)
        max_count = gdf['count'].max()
    else:
        min_count = q1_count = median_count = q3_count = max_count = "N/A"

    # Display summary statistics in Streamlit
    st.subheader("Summary Statistics")
    st.write(f"**Total Routes:** {total_routes}")
    st.write(f"**Trip Count (Min / Q1 / Median / Q3 / Max):** {min_count} / {q1_count:.2f} / {median_count} / {q3_count:.2f} / {max_count}")


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

# Dropdown for quarter selection
selected_quarter = st.sidebar.selectbox("Select a 2024 Quarter:", list(QUARTER_FILES.keys()), index=1)

# Load data from local file system
@st.cache_data
def load_geojson(file_path):
    return gpd.read_file(file_path)

# Get max trip count for filtering
max_trip_count = int(gdf['count'].max()) if 'count' in gdf.columns else 50

# Numeric input for filtering (forcing bounds)
min_trip_count = st.sidebar.number_input(
    "Filter to only show routes with at least X scooter trips passing through it during the quarter:", 
    min_value=0, 
    max_value=max_trip_count, 
    value=min(4500, max_trip_count),  # Default value
    step=1
)

# Button to apply filter
if "filter_applied" not in st.session_state:
    st.session_state.filter_applied = False  # Initialize session state

if st.sidebar.button("Apply Filter"):
    st.session_state.filter_applied = True  # Update session state
    gdf = load_geojson(QUARTER_FILES[selected_quarter]) # Fetch and load the selected dataset
    gdf = gdf[gdf['count'] >= min_trip_count]  # Apply filtering

# Display content based on whether the filter is applied
if not st.session_state.filter_applied:
    st.subheader("About this website")
    st.write(
        "Welcome to Ryan Lohbrunner's **Micromobility Data Analysis** tool! 🛴📊\n\n"
        "Use the filters in the sidebar to select a quarter and specify a minimum trip count. "
        "A few seconds (~5-20) after applying the filter, an interactive map will pop up and display the scooter routes "
        "in the city, along with key statistics. This web app is currently under development and will include new "
        "features, cities, time periods, vehicle types, and data tools within the upcoming weeks. "
        "Data ~~stolen~~ scraped from Ride Report, found at public.ridereport.com.")
else:
    st.subheader("Routes")
    map_output = plot_linestrings(gdf)
    folium_static(map_output)
    # Display summary statistics
    summary_statistics(gdf)
