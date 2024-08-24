# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.4
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
"Generate image with flight track superimposed on GOES visible image"""

from orcestra.flightplan import  LatLon, path_preview
from orcestra.weathermaps import goes_overlay
import matplotlib.pyplot as plt
import seaborn as sns
import cartopy.crs as ccrs
import xarray as xr

sns.set_context("talk")

flight_name = 'HALO-20240818a'
flight_date = flight_name[5:9]+'-'+flight_name[9:11]+'-'+flight_name[11:13]
tracks = xr.open_dataset('/Volumes/ORCESTRA/'+flight_name+'/bahamas/QL_'+flight_name+'_BAHAMAS_V01.nc')
path   = LatLon(lat=tracks['IRS_LAT'], lon=tracks['IRS_LON'], label=flight_name)

fig, ax = plt.subplots(
    figsize=(15, 8),
    facecolor='white',
    subplot_kw  ={"projection": ccrs.PlateCarree()}
)

path_preview(path,ax=ax,show_waypoints=False,color='#FF5349')

# goes_overlay can take some time depending on the network.  The downloaded image is cached, but the first time
# it can take 15 min to download.  Thereafter the fetching and plotting of the cached data takes about 1 min
#
goes_overlay(flight_date+'T14:15',ax)
fig.savefig(flight_name+'-track.jpeg',bbox_inches='tight')
