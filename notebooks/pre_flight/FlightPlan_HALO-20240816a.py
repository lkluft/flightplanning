# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
import cartopy.crs as ccrs
import csv
from dataclasses import asdict
from datetime import datetime, timedelta
import easygems.healpix as egh
import intake
import matplotlib.pyplot as plt
import numpy as np
import orcestra
import orcestra.flightplan as fp
import orcestra.sat
from orcestra.flightplan import LatLon, IntoCircle, bco, sal
import pandas as pd


# %%
# Function that finds longitude of ec track that corresponds to the provided latitude
def find_ec_lon(lat_sel, ec_lons, ec_lats):
    return ec_lons[np.argmin(np.abs(ec_lats-lat_sel))]


# %%
# Define dates for forecast initialization and flight

issued_time = datetime(2024, 8, 12, 12, 0, 0)
issued_time_str = issued_time.strftime('%Y-%m-%d')

flight_time = datetime(2024, 8, 16, 12, 0, 0)
flight_time_str = flight_time.strftime('%Y-%m-%d')
flight_index = f"HALO-{flight_time.strftime('%Y%m%d')}a"

print("Initalization date of IFS forecast: " + issued_time_str + "\nFlight date: " + flight_time_str + "\nFlight index: " + flight_index)

# %%
# Domain definition
# TO DO: replace by global definition once it exists
lon_min, lon_max, lat_min, lat_max = -65, -5, -10, 25

# %%
# Load forecast data
cat = intake.open_catalog("https://tcodata.mpimet.mpg.de/internal.yaml")
ds = cat.HIFS(refdate=issued_time_str, reftime=issued_time.hour).to_dask().pipe(egh.attach_coords)

# %%
# Load ec satellite track for 
track = orcestra.sat.SattrackLoader("EARTHCARE", "2024-08-12", kind="PRE").get_track_for_day(flight_time_str)
track = track.sel(time=slice(flight_time_str + " 06:00", None))
ec_lons, ec_lats = track.lon.values, track.lat.values

# %% [markdown]
# **Waypoint definitions**

# %%
# Mass flux circle radius (m)
radius = 130e3
atr_radius = 70e3

# %%
# Setting region (Cabo Verde vs. Barbados)
band = "east"
airport = sal if band == "east" else bco

# %%
# Latitudes where we enter ec track (visually estimated)
lat_north = 15.0
lat_south = 4.0

# %%
# ITCZ edges visually estimated from iwv contours
lat_edge_south = 5.0
lat_edge_north = 12.7

# %%
# Setting lat/lon coordinates

# Points where we get on ec track
north_ec = LatLon(lat_north, find_ec_lon(lat_north, ec_lons, ec_lats), "north_ec")
south_ec = LatLon(lat_south, find_ec_lon(lat_south, ec_lons, ec_lats), "south_ec")

# Intersection of ITCZ edges with ec track
circle_north = LatLon(lat_edge_north, find_ec_lon(lat_edge_north, ec_lons, ec_lats), "circle_north")
circle_south = LatLon(lat_edge_south, find_ec_lon(lat_edge_south, ec_lons, ec_lats), "circle_south")

# Center of middle circle
circle_center = circle_south.towards(circle_north).assign_label("circle_center")

# EarthCARE meeting point between circles
earthcare = circle_south.towards(circle_center).assign_label("earthcare")

# ATR
atr = LatLon(17.8, -22.0, "atr")

# Define flight track, can be split into different legs
leg_south = [
     airport, 
     north_ec,
     south_ec
]

leg_circles = [
     IntoCircle(circle_south, radius, 360),   
     earthcare,
     IntoCircle(circle_center, radius, 360), 
     IntoCircle(circle_north, radius, 360),
]    

leg_home = [
     north_ec,
     IntoCircle(atr, atr_radius, -360, enter = 30),
     airport
]

waypoints = leg_south + leg_circles + leg_home 

path = fp.expand_path(waypoints, dx=10e3)

# %%
plt.figure(figsize = (12, 8))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
ax.coastlines(alpha=1.0)
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

cwv_flight_time = ds["tcwv"].sel(time=flight_time, method = "nearest")
fp.plot_cwv(cwv_flight_time, levels = [45.0, 48.0, 50.0])
plt.title(cwv_flight_time.time.values)

plt.plot(ec_lons, ec_lats)
fp.plot_path(path, ax, color="C1")

# %%
pd.DataFrame.from_records(map(asdict, [north_ec, circle_north, circle_center, circle_south, south_ec, earthcare, atr])).set_index("label")

# %%
from tabulate import tabulate

def decimal_to_degrees_minutes(decimal):
    degrees = int(decimal)
    minutes = abs(decimal - degrees) * 60
    return f"{degrees}° {minutes:.2f}'".replace('.', ',')

table = []

for point in waypoints:
    if isinstance(point, IntoCircle):
        point = point.center
    lat_deg_min = decimal_to_degrees_minutes(point.lat)
    lon_deg_min = decimal_to_degrees_minutes(point.lon)
    table.append([point.label, lat_deg_min, lon_deg_min, f"{point.lat:.4f}".replace('.', ','), f"{point.lon:.4f}".replace('.', ',')])

# Print the table with headers
print(tabulate(table, headers=["Label", "Latitude ", "Longitude", "Latitude (decimal)", "Longitude (decimal)"], tablefmt="pretty", colalign=("left", "right", "right", "right", "right")))

# Save the table to a CSV file
csv_file = f"{flight_index}_waypoints.csv"
with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Label", "Latitude", "Longitude", "Latitude (decimal)", "Longitude (decimal)"])  # Writing the header
    writer.writerows(table)  # Writing the table data

print(f"Table saved to {csv_file}")

# %%
