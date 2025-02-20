import geopandas as gpd
import pandas as pd
import numpy as np





gdf = gpd.read_file("data/routes_Q2.geojson")
# Replace "< 100" with 50
gdf['count'] = gdf['count'].fillna(50)
# Convert to int
gdf['count'] = [int(count) for count in gdf['count']]
max_count = int(gdf['count'].max())
min_count = int(gdf['count'].min())
unique_count = gdf['count'].unique()
print(unique_count)

print(max_count)
print(min_count)

index_list = list(range(min_count, max_count, ((max_count-min_count)//5)))
print(index_list)

        # Compute quartile breaks for Step Colormap
        quantiles = np.percentile(gdf['count'], [20, 40, 60, 80, 100])
        color_steps = ['#53bf7f', '#a2d9ce', '#85c1e9', '#bd8cd2', '#572a6a']
        # Define StepColormap based on quantiles
        colormap = cm.StepColormap(
            colors=color_steps,
            index=quantiles.tolist(),  # Ensure step values match percentiles
            vmin=quantiles[0], vmax=quantiles[-1]
        )
