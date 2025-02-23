# Dashboard/UI Functions (?)
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
import matplotlib.pyplot as plt

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
        
        color_steps = ['#a2d9ce', '#53bf7f', '#85c1e9', '#bd8cd2', '#572a6a']
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
    st.write(f"**Total Route Segments in Selection:** {total_routes}")
    st.write(f"**Per Segment Trip Count (Min / Q1 / Median / Q3 / Max):** {min_count:.0f} / {q1_count:.0f} / {median_count:.0f} / {q3_count:.0f} / {max_count:.0f}")


def plot_trip_count_histogram(gdf):
    """
    Plots a histogram of trip counts for route segments.

    Parameters:
        gdf (GeoDataFrame): Data containing the 'count' column.

    Returns:
        None (Displays histogram in Streamlit)
    """
    if 'count' in gdf.columns:
        st.subheader("Trip Count Distribution")
        
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(gdf['count'], bins=30, color='#3498db', edgecolor='black', alpha=0.7)
        
        ax.set_xlabel("Number of Trips")
        ax.set_ylabel("Number of Segments")
        ax.set_title("Distribution of Trip Counts Across Route Segments")

        st.pyplot(fig)

def plot_trip_count_histogram_flipped(gdf):
    """
    Plots a flipped histogram where the y-axis represents trip count bins, and
    the x-axis represents the number of segments in each bin.

    Parameters:
        gdf (GeoDataFrame): Data containing the 'count' column.

    Returns:
        None (Displays histogram in Streamlit)
    """
    if 'count' in gdf.columns:
        st.subheader("Trip Count Distribution (Flipped)")

        # Compute histogram bins
        bins = np.histogram_bin_edges(gdf['count'], bins=30)  # Create bins
        hist, bin_edges = np.histogram(gdf['count'], bins=bins)  # Get counts per bin

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(bin_edges[:-1], hist, height=np.diff(bin_edges), color='#3498db', edgecolor='black', alpha=0.7)

        ax.set_ylabel("Trip Count Bins")  # Y-axis now represents trip count bins
        ax.set_xlabel("Number of Segments")  # X-axis represents the count of segments per bin
        ax.set_title("Distribution of Segments by Trip Count Bins")

        st.pyplot(fig)
