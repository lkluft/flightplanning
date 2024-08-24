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
# %load_ext autoreload
# %autoreload 2

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
from orcestra.flightplan import LatLon, IntoCircle, bco, sal, mindelo, find_ec_lon, vertical_preview, to_kml
import pandas as pd

# %%
# Define dates for forecast initialization and flight

issued_time = datetime(2024, 8, 22, 0, 0, 0)

flight_time = datetime(2024, 8, 25, 12, 0, 0)
flight_index = f"HALO-{flight_time.strftime('%Y%m%d')}a"

print(
    f"Initalization date of IFS forecast: {issued_time}\n"
    f"Flight date: {flight_time:%Y-%m-%d}\n"
    f"Flight index: {flight_index}"
)

# %%
# Domain definition
# TO DO: replace by global definition once it exists
lon_min, lon_max, lat_min, lat_max = -65, -5, -10, 25

# %%
# Load forecast data
cat = intake.open_catalog("https://tcodata.mpimet.mpg.de/internal.yaml")
ds = cat.HIFS(datetime = issued_time).to_dask().pipe(egh.attach_coords)

# %%
# Load ec satellite track for 
ec_track = orcestra.sat.SattrackLoader("EARTHCARE", "2024-08-21", kind="PRE").get_track_for_day(f"{flight_time:%Y-%m-%d}")
ec_track = ec_track.sel(time=slice(f"{flight_time:%Y-%m-%d} 06:00", None))
ec_lons, ec_lats = ec_track.lon.values, ec_track.lat.values


# %%
def ec_time_at_lat(ec_track, lat):
    e = np.datetime64("2024-08-01")
    s = np.timedelta64(1, "ns")
    return (((ec_track.swap_dims({"time":"lat"}).time - e) / s).interp(lat=lat) * s + e)


# %% [markdown]
# **Waypoint definitions**

# %%
# Mass flux circle radius (m)
radius = 130e3
atr_radius = 70e3

# Setting region (Cabo Verde vs. Barbados)
airport = sal #bco

# Latitudes where we enter and leave the ec track (visually estimated)
lat_ec_north_out = 16.0
lat_ec_north_in = 12.0
lat_ec_south = 2.5

# ITCZ edges visually estimated from iwv contours
lat_c_south = 4.0
lat_c_north = 10.0

# Extra Points to give some flexibility with the circle locations
lat_c_south_alt_s = 3.25
lat_c_south_alt_n = 4.75

lat_c_north_alt_s = 9.25
lat_c_north_alt_n = 10.75

# %%
# Setting lat/lon coordinates

# Points where we get on ec track
north_ec_in = LatLon(lat_ec_north_in, find_ec_lon(lat_ec_north_in, ec_lons, ec_lats), label = "north_ec_in")
north_ec_out = LatLon(lat_ec_north_out, find_ec_lon(lat_ec_north_out, ec_lons, ec_lats), label = "north_ec_out")
south_ec = LatLon(lat_ec_south, find_ec_lon(lat_ec_south, ec_lons, ec_lats), label = "south_ec")

# Intersection of ITCZ edges with ec track
c_north = LatLon(lat_c_north, find_ec_lon(lat_c_north, ec_lons, ec_lats), label = "c_north")
c_south = LatLon(lat_c_south, find_ec_lon(lat_c_south, ec_lons, ec_lats), label = "c_south")

# Center of middle circle
c_mid = c_south.towards(c_north).assign(label = "c_mid")

# EarthCARE underpass
ec_under = c_north.towards(north_ec_out).assign(label = "ec_under")

# ATR circle
atr_circ = LatLon(17.433, -23.5, label = "atr")
atr_circ_alt = LatLon(lat=16.084, lon=-21.819, label="atr_alt")

# Extra Points along the way
c_south_alt_s = LatLon(lat_c_south_alt_s, find_ec_lon(lat_c_south_alt_s, ec_lons, ec_lats), label = "c_south_alt_s")
c_south_alt_n = LatLon(lat_c_south_alt_n, find_ec_lon(lat_c_south_alt_n, ec_lons, ec_lats), label = "c_south_alt_n")

c_north_alt_s = LatLon(lat_c_north_alt_s, find_ec_lon(lat_c_north_alt_s, ec_lons, ec_lats), label = "c_north_alt_s")
c_north_alt_n = LatLon(lat_c_north_alt_n, find_ec_lon(lat_c_north_alt_n, ec_lons, ec_lats), label = "c_north_alt_n")

# Define flight track, can be split into different legs
waypoints = [
     airport.assign(time='2024-08-25T09:30:00Z'), 
     north_ec_in.assign(fl=400),
     c_north.assign(fl=400),
     c_mid.assign(fl=400),
     c_south.assign(fl=400),
     south_ec.assign(fl=430),
     c_south_alt_s.assign(fl=430),
     IntoCircle(c_south.assign(fl=430), radius, 360),  
     c_south_alt_n.assign(fl=430),
     IntoCircle(c_mid.assign(fl=430), radius, 360), 
     c_north_alt_s.assign(fl=430),
     IntoCircle(c_north.assign(fl=450), radius, 360),
     c_north_alt_n.assign(fl=450),
     ec_under.assign(fl=450),
     north_ec_out.assign(fl=450),
     mindelo.assign(fl=450),
     IntoCircle(atr_circ_alt.assign(fl=350), atr_radius, 360),
     airport
] 

path = fp.expand_path(waypoints, dx=10e3)

# %%
plt.figure(figsize = (12, 8))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
ax.coastlines(alpha=1.0)
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

cwv_flight_time = ds["tcwv"].sel(time=flight_time, method = "nearest")
fp.plot_cwv(cwv_flight_time, levels = [45.0, 48.0, 50.0, 52.0, 54.0])
plt.title(f"{flight_time}\n(CWV forecast issued on {issued_time})")

plt.plot(ec_lons, ec_lats)
fp.plot_path(path, ax, color="C1")

# %% [markdown]
# crew:
#   - name: Julia Windmiller
#     job: PI
#   - name: Tanja Bodenbach
#     job: WALES
#   - name: Jakob Deutloff
#     job: HAMP
#   - name: Theresa Mieslinger
#     job: Dropsondes
#   - name: Kevin Wolf
#     job: Smart/VELOX
#   - name: tbd
#     job: SpecMACS
#   - name: Suelly Katiza
#     job: Scientist
#   - name: Nicolas Rochetin
#     job: Ground contact

# %%
vertical_preview(waypoints)
plt.ylabel("Flight level")
plt.xlabel("Distance / m")

# %%
path.isel(distance = path.waypoint_indices).to_dataframe().set_index("waypoint_labels")

# %%
with open(f"{flight_index}.kml", "w") as f:
    f.write(to_kml(path))

# %%
points_fx_DM = []
points_fx_DMmm = []

for point in waypoints:
    
    if isinstance(point, IntoCircle):
        point = point.center
        
    points_fx_DM.append(point.format_1min())
    points_fx_DMmm.append(point.format_pilot())

output_file = f"waypoints_{flight_index}.txt"

with open(output_file, "w") as file:
    file.write("DM\n")
    file.write(" ".join(points_fx_DM) + "\n")
    file.write("DMmm\n")
    file.write(" ".join(points_fx_DMmm) + "\n")
