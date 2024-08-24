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
from importlib import reload
import intake
import matplotlib.pyplot as plt
import numpy as np
import orcestra
import orcestra.flightplan as fp
import orcestra.sat
from orcestra.flightplan import LatLon, IntoCircle, bco, sal, find_ec_lon
import pandas as pd

# %%

# %% [raw]
#

# %%
# Define dates for forecast initialization and flight
# Airport Restrictions. None for 18.8.
# Meet EarthCARE South of ITCZ or in the South of the ITCZ (if there is less clouds)  (Silke)

issued_time = datetime(2024, 8, 14,0, 0, 0)   # ???
issued_time_str = issued_time.strftime('%Y-%m-%d')

flight_time = datetime(2024, 8, 18, 10, 0, 0)         # ??? start date and time
flight_time_str = flight_time.strftime('%Y-%m-%d')
flight_index = f"HALO-{flight_time.strftime('%Y%m%d')}a"

print("Initalization date of IFS forecast: " + issued_time_str + "\nFlight date: " + flight_time_str + "\nFlight index: " + flight_index)

# %%
# Domain definition
# TO DO: replace by global definition once it exists
lon_min, lon_max, lat_min, lat_max = -65, -5, -5, 25

# %%
# Load forecast data
cat = intake.open_catalog("https://tcodata.mpimet.mpg.de/internal.yaml")
ds = cat.HIFS(refdate="2024-08-15",reftime="00").to_dask().pipe(egh.attach_coords)   # ???

# %%
# Load ec satellite track for 
track = orcestra.sat.SattrackLoader("EARTHCARE", "2024-08-16", kind="PRE").get_track_for_day(flight_time_str)
track = track.sel(time=slice(flight_time_str + " 06:00", None))
ec_lons, ec_lats = track.lon.values, track.lat.values

# %%

# %% [markdown]
# **Waypoint definitions**

# %%
track.lat

# %%
track.time

# %%
# Mass flux circle radius (m)
radius = 100e3

# %%
# ITCZ edges visually estimated from iwv contours

lat_edge_south = 3.0    # ???
lat_edge_north = 13.1   # ???

# %%
# # ?
band = "east"

airport = sal if band == "east" else bco

# Point where we enter ec track? visually estimated? Rename to "lat_track_entry_north"?
lat_north = 14.0 # 10th percentile     #???
lat_south = 3.0 # 5th percentile - 1°  #??? 

# %%
# Setting lat/lon coordinates

# Points where we get on ec track?
north = LatLon(lat_north, find_ec_lon(lat_north, ec_lons, ec_lats), "north")
south = LatLon(lat_south, find_ec_lon(lat_south, ec_lons, ec_lats), "south")

# Intersection of ITCZ edges with ec track
edge_north = LatLon(lat_edge_north, find_ec_lon(lat_edge_north, ec_lons, ec_lats), "edge_north")
edge_south = LatLon(lat_edge_south, find_ec_lon(lat_edge_south, ec_lons, ec_lats), "edge_south")

# Center of middle circle
center = edge_south.towards(edge_north).assign_label("center")

# Southern return point
returnPoint = north if band == "east" else LatLon(bco.lat, -53.0, "")


# What does leg refer to?
leg_south = [
     airport,
     north,
     edge_north,
     center,
     edge_south,
     south
]

leg_circles = [
     IntoCircle(edge_south, radius, 360),
     IntoCircle(center, radius, 360),
     IntoCircle(edge_north, radius, 360),
]
    
leg_home = [
     north,
     airport
]

waypoints = leg_south + leg_circles + leg_home 

path = fp.expand_path(waypoints, dx=10e3)

#print(f"duration: {halo_flight_duration(path)}")

# %%
path.distance

# %%
plt.figure(figsize = (12, 8))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
ax.coastlines(alpha=1.0)
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)


cwv_flight_time = ds["tcwv"].sel(time=flight_time, method = "nearest")
fp.plot_cwv(cwv_flight_time, levels = [48.0, 50.0, 52.0])
plt.title(f"{flight_time_str} \n (CWV forecast issued on {issued_time_str})")

plt.plot(ec_lons, ec_lats)
fp.plot_path(path, ax, color="C1")

# %%
pd.DataFrame.from_records(map(asdict, [north, edge_north, center, edge_south, south])).set_index("label")

# %%
path

# %%

# %%

# %%
