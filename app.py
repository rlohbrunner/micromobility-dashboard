import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from shapely.geometry import LineString 
import branca.colormap as cm
import random
import streamlit as st
from streamlit_folium import folium_static

# Streamlit UI
st.title("Micromobility Route Analysis")
st.sidebar.header("Upload Data")

# File uploader
uploaded_file = st.sidebar.file_uploader("Upload a .geojson file", type=["geojson"])

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
      gdf['count'] = gdf['count'].fillna(1)  # Avoid log(0)
      gdf['percentage'] = gdf['percentage'].fillna(1)  # Default to small width
      # Compute quartile breaks for Step Colormap
      quantiles = np.percentile(gdf['count'], [60, 80, 95, 99, 99.5, 99.95])
      color_steps = ['#53bf7f', '#a2d9ce', '#85c1e9', '#bd8cd2', '#7d3c98', '#572a6a']
      # Define StepColormap based on quantiles
      colormap = cm.StepColormap(
          colors=color_steps,
          index=quantiles.tolist(),  # Ensure step values match percentiles
          vmin=quantiles[0], vmax=quantiles[-1]
          #vmin=gdf['count'].min(), vmax=gdf['count'].max()
      )
      # Normalize percentage for line width scaling
      min_percentage, max_percentage = gdf['percentage'].min(), gdf['percentage'].max()
      def scale_width(value, min_val, max_val):
          """Scales line width between 1 and 5 based on percentage."""
          return 4 + 8 * ((value - min_val) / (max_val - min_val) if max_val > min_val else 1)
      # Add line geometries to the map with colors & widths
      for _, row in gdf.iterrows():
          if row.geometry.geom_type == 'LineString':
              coords = [(point[1], point[0]) for point in row.geometry.coords]  # folium uses (lat, lon)
              color = colormap(row['count'])  # ✅ Step colormap applied
              width = scale_width(row['percentage'], min_percentage, max_percentage)  # Scale width
              folium.PolyLine(coords, color=color, weight=width, opacity=0.8, 
                              tooltip=f"Count: {row['count']}, Percentage: {row['percentage']}").add_to(m)
      # Fix colormap legend to show quartile step values
      colormap.caption = "Trip Density"
      colormap.add_to(m)
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



if uploaded_file:
    gdf = gpd.read_file(uploaded_file)
    # top_1_gdf = filter_top_1_percent(gdf)
    # merged_gdf = merge_connected_segments(top_1_gdf)
    st.subheader("Routes")
    map_output = plot_linestrings(gdf)
    folium_static(map_output)
    # Display summary statistics
    summary_statistics(gdf)
