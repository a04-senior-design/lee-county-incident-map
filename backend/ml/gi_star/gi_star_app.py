"""
This module is the driver script for generating a Gi*-based incident heat map.
It loads incident location data and instantiates a GiStarHeatMap object to
generate a PNG heat map image.  This image is then overlaid onto a folium map,
a Python wrapper around the Leaflet JavaScript library.
"""


import os

import pandas as pd
import numpy as np
import geopandas as gpd
from pyproj import Transformer
import folium
import branca.colormap as bcm

from GiStarHeatMap import GiStarHeatMap


#----------------------Gi-Star heatmap overlay generated below--------------------------------------------------------------------

def load_points() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load incidents from the CSV and return a (N, 2) array of projected x-y
    coordinates suitable for euclidean distance, plus the original latitude
    and longitude arrays.
    """

    incidents_df = pd.read_csv(CSV_PATH).dropna(subset=["lat", "lon"])
    
    latitude = incidents_df["lat"].to_numpy()
    longitude = incidents_df["lon"].to_numpy()

    # NAD 1983 StatePlane Florida West FIPS 0902 Feet
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2882", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    points = np.column_stack([easting, northing])
    
    return points, latitude, longitude


#CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv")
CSV_PATH = os.path.join(
    os.path.dirname(__file__), 
    "late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv"
)

# input data based on a sample of x-y coordinates (easting/northing) from County incident data
data_points, latitude, longitude = load_points()
easting = data_points[:, 0]
northing = data_points[:, 1]

# define the range of the grid to represent the corresponding map coordinates
cell_size = 5000
padding = cell_size
x_min = np.min(easting) - padding
x_max = np.max(easting) + padding
y_min = np.min(northing) - padding
y_max = np.max(northing) + padding


# HAVE BACKEND READ THIS FILE ONCE UPON STARTUP

# land polygon from the county land mask shapefile (the "WATER" type features are ignored)
LAND_MASK_PATH = os.path.join(os.path.dirname(__file__), "CountyBackground_Land_Mask", "CountyBackground.shp")
land_gdf = gpd.read_file(LAND_MASK_PATH)
land_gdf = land_gdf[land_gdf["TYPE"] == "LAND"].to_crs("EPSG:2882")
# make_valid repairs the invalid LAND polygon before the pieces are merged
land_polygon = land_gdf.geometry.make_valid().union_all()



# distance_band will be adjustable by the user
distance_band = 1.5 * cell_size
# instantiate a GiStarHeatMap object
gi_star_obj = GiStarHeatMap(points=data_points, distance_band=distance_band, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, cell_size=cell_size, land_polygon=land_polygon, output_dir=".")
# generate the heat map overlay PNG image file and get its latitude/longitude boundaries
bounds = gi_star_obj.generate_zscore_heatmap_image()
print(f'bounds:  {bounds}')



#----------------------API functionality below--------------------------------------------------------------------

# API will transmit PNG image file (as URL or base64-encoded string) and boundary coordinates to frontend as JSON

#----------------------Frontend functionality below---------------------------------------------------------------


# create a map centered on the boundaries of the Gi* z-score surface
m = folium.Map(location=[(bounds.top + bounds.bottom)/2, (bounds.left + bounds.right)/2], zoom_start=12)

legend_style = """
<style>
    .legend {
        background-color: white !important;
        padding: 10px !important;
        border-radius: 5px !important;
        box-shadow: 0 0 6px rgba(0,0,0,0.4) !important;
    }
</style>
"""
m.get_root().html.add_child(folium.Element(legend_style))

# lay the colorized PNG image of the lat/long re-projected tif file onto the map
folium.raster_layers.ImageOverlay(
    image="z_score_overlay.png",
    bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
    opacity=0.8,
).add_to(m)

# build a branca LinearColormap from the JSON-serializable legend data,
# so folium's legend matches exactly what the frontend renders
legend_data = gi_star_obj.get_legend_data()
legend = bcm.LinearColormap(
    colors=legend_data["colors"],
    vmin=legend_data["vmin"],
    vmax=legend_data["vmax"],
    caption=legend_data["caption"],
    tick_labels=legend_data["ticks"],
)
legend.add_to(m)

m.save("gi-star-heatmap.html")






