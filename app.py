import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
import branca.colormap as cm
import random
from shapely.geometry import LineString
from streamlit_folium import folium_static

# Streamlit UI
st.title("Micromobility Route Analysis")
st.sidebar.header("Upload Data")

# File uploader
uploaded_file = st.sidebar.file_uploader("Upload a .geojson file", type=["geojson"])

def filter_top_1_percent(gdf):
    gdf['count'] = gdf['count'].fillna(0)
    threshold = np.percentile(gdf['count'], 99)
    return gdf[gdf['count'] >= threshold].copy()

def merge_connected_segments(gdf):
    def round_coords(coord):
        return (round(coord[0], 3), round(coord[1], 3))
    
    gdf['first_coord'] = gdf['geometry'].apply(lambda x: round_coords(x.coords[0]))
    gdf['last_coord'] = gdf['geometry'].apply(lambda x: round_coords(x.coords[-1]))
    
    segment_groups = []
    visited = set()
    
    def build_super_segment(segment_idx, current_coords):
        if segment_idx in visited:
            return
        visited.add(segment_idx)
        current_coords.extend(list(gdf.loc[segment_idx, 'geometry'].coords)[1:])
        next_segments = gdf[gdf['first_coord'] == gdf.loc[segment_idx, 'last_coord']].index.tolist()
        for next_idx in next_segments:
            build_super_segment(next_idx, current_coords)
    
    for idx in gdf.index:
        if idx not in visited:
            super_segment_coords = list(gdf.loc[idx, 'geometry'].coords)
            build_super_segment(idx, super_segment_coords)
            segment_groups.append(LineString(super_segment_coords))
    
    return gpd.GeoDataFrame(geometry=segment_groups, crs=gdf.crs)

def plot_linestrings(gdf):
    gdf = gdf.to_crs(epsg=4326)
    projected_gdf = gdf.to_crs(epsg=32616)
    center_lat = projected_gdf.geometry.centroid.to_crs(epsg=4326).y.median()
    center_lon = projected_gdf.geometry.centroid.to_crs(epsg=4326).x.median()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB Positron")
    
    if 'count' in gdf.columns:
        gdf['count'] = gdf['count'].fillna(1)
        gdf['percentage'] = gdf['percentage'].fillna(1)
        quantiles = np.percentile(gdf['count'], [60, 80, 95, 99, 99.5, 99.95])
        color_steps = ['#53bf7f', '#a2d9ce', '#85c1e9', '#bd8cd2', '#7d3c98', '#572a6a']
        colormap = cm.StepColormap(colors=color_steps, index=quantiles.tolist(), vmin=quantiles[0], vmax=quantiles[-1])
        min_percentage, max_percentage = gdf['percentage'].min(), gdf['percentage'].max()
        
        def scale_width(value, min_val, max_val):
            return 4 + 8 * ((value - min_val) / (max_val - min_val) if max_val > min_val else 1)
        
        for _, row in gdf.iterrows():
            if row.geometry.geom_type == 'LineString':
                coords = [(point[1], point[0]) for point in row.geometry.coords]
                color = colormap(row['count'])
                width = scale_width(row['percentage'], min_percentage, max_percentage)
                folium.PolyLine(coords, color=color, weight=width, opacity=0.8, tooltip=f"Count: {row['count']}, Percentage: {row['percentage']}").add_to(m)
        
        colormap.caption = "Trip Density"
        colormap.add_to(m)
    
    return m

if uploaded_file:
    gdf = gpd.read_file(uploaded_file)
    top_1_gdf = filter_top_1_percent(gdf)
    merged_gdf = merge_connected_segments(top_1_gdf)
    
    st.subheader("Filtered and Merged Routes")
    map_output = plot_linestrings(merged_gdf)
    folium_static(map_output)
