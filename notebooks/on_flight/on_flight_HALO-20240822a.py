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

# %% [markdown]
# # Ground support script
#
# Makes some useful figures to track convection etc

# %%
# Import a bunch of stuff


# Utilities
from datetime import datetime, timedelta
import intake
import os
import requests
from io import BytesIO

# Orcestra
from orcestra.flightplan import sal, bco, LatLon, IntoCircle, path_preview, plot_cwv, plot_path,find_ec_lon
from orcestra.utils import export_planet
import orcestra.sat as sattrack

# Satelite data
from goes2go.data import goes_nearesttime, goes_latest
from goes2go.tools import abi_crs
import goes


# The usual plotting business and array business
import matplotlib as mpl
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import pandas as pd
import numpy as np

# Image stuff
from PIL import Image



  

# %% [markdown]
# ## Set these parameters

# %%
# Set the time of this flight
take_off_time = datetime(2024, 8, 22, 12, 0, 0)
take_off_time_str = take_off_time.strftime('%Y-%m-%d')


flight_id = 'HALO-' + take_off_time.strftime('%Y%m%d') +'a'

# Set the last forecast time for IFS
forecast_initialisation_time = datetime(2024, 8, 21, 12, 0, 0)

# Example of using timedelta
current_time = datetime.utcnow()
time_two_hours_ago = current_time - timedelta(hours=2)


# %%
def make_output_dir(output_type):
   if not os.path.exists("./Figures/"+flight_id+"/"+output_type): 
       os.makedirs("./Figures/"+flight_id+"/"+output_type) 

make_output_dir('TCWV_forecast')
make_output_dir('VIS')
make_output_dir('IR')
make_output_dir('VIS_and_TPW')
make_output_dir('TPW')
make_output_dir('AOD')
make_output_dir('WV')
make_output_dir('Planet')



# %% [markdown]
# ### First get the flight path
#
# Can download this from here: https://orcestra-campaign.org/operation/halo.html

# %%
# Get the flight plan
# Download from: https://orcestra-campaign.org/operation/halo.html

# Load ec satellite track for
track = sattrack.SattrackLoader("EARTHCARE", "2024-08-19", kind="PRE").get_track_for_day(take_off_time_str)
track = track.sel(time=slice(take_off_time_str + " 06:00", None))
ec_lons, ec_lats = track.lon.values, track.lat.values

radius = 1.852 * 72e3 # factor of 1.852 is km/nm (definition)
atr_radius = 1.852 * 38e3 

airport = sal

lat_north = 19.0
lat_south = 4.0

lat_edge_north = 13.3
lat_edge_center = 9.5
lat_edge_south = 6.0

lat_north_ec = 17.0
lat_meet_ec = 15.75
lat_south_ec = 14.5

lat_mindelo =  16.877833
lon_mindelo = -24.994975

lat_atr_circle_ec = 17.7

# Setting lat/lon coordinates

# Points where we get on ec track?
north_ec = LatLon(lat_north, find_ec_lon(lat_north, ec_lons, ec_lats),)
south_ec = LatLon(lat_south, find_ec_lon(lat_south, ec_lons, ec_lats),)

# Points where to meet atr and earthcare
north_ec_atr = LatLon(lat_north_ec, find_ec_lon(lat_north_ec, ec_lons, ec_lats),)
meet_ec_atr = LatLon(lat_meet_ec, find_ec_lon(lat_meet_ec, ec_lons, ec_lats), )
south_ec_atr = LatLon(lat_south_ec, find_ec_lon(lat_south_ec, ec_lons, ec_lats),)

# Intersection of ITCZ edges with ec track
circle_north = LatLon(lat_edge_north, find_ec_lon(lat_edge_north, ec_lons, ec_lats), )

circle_center = LatLon(lat_edge_center, find_ec_lon(lat_edge_center, ec_lons, ec_lats),)

circle_south = LatLon(lat_edge_south, find_ec_lon(lat_edge_south, ec_lons, ec_lats),)

circle_atr_ec = LatLon(lat_atr_circle_ec, find_ec_lon(lat_atr_circle_ec, ec_lons, ec_lats),)

mindelo = LatLon(lat_mindelo, lon_mindelo, )



leg_south = [
     airport,
     north_ec_atr,
     north_ec,
     IntoCircle(circle_atr_ec, atr_radius, 360),
     north_ec_atr,
     meet_ec_atr,
     south_ec_atr,
     circle_north,
     circle_center,
     circle_south,
     south_ec
]

leg_circles = [
     IntoCircle(circle_south, radius, 360),
     IntoCircle(circle_center, radius, 360),
     IntoCircle(circle_north, radius, 360),
]
    
leg_home = [
     south_ec_atr,
     mindelo,
     IntoCircle(circle_atr_ec, atr_radius, 360),
     airport
]

path = leg_south + leg_circles + leg_home 



# %% [markdown]
# ### Now plot the forecast column water vapour

# %%
# Get the IFS forecast 
cat = intake.open_catalog("https://tcodata.mpimet.mpg.de/internal.yaml")

ds = cat.HIFS(datetime=forecast_initialisation_time.strftime('%Y-%m-%d %H:%M')).to_dask()


# %%
# PLot the column water vapour


# Select the one closest to current time
current_time = datetime.utcnow()
cwv_latest = ds["tcwv"].sel(time=current_time, method = "nearest")
time_of_cwv = ds["time"].sel(time=current_time, method = "nearest")

# Plot the flight path
ax = path_preview(path)

# PLot the column water vapour
plot_cwv(cwv_latest,levels=[45,48,50])

the_title = 'Valid: ' + str(time_of_cwv.values.astype('datetime64[m]')) + ', issued: ' + str(forecast_initialisation_time.strftime('%Y-%m-%dT%H:%M'))

plt.title(the_title)

export_planet('./Figures/'+flight_id+'/TCWV_forecast/TCWV_' + str(time_of_cwv.values.astype('datetime64[m]')) + '.png',dpi=100)


# %% [markdown]
# ## Now plot GOES snapshots
#
# ### Visible

# %%
# Use NASA world view to get the most recent GOES visible image and plot it


# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_vis(current_time_pd)
ax = plt.gca()
sat_time = sat_time[:-4]+'Z'

# Plot the flight path
plot_path(path,ax=ax,color='orange')

ax.annotate(sat_time, (-12, 1), backgroundcolor="white")

export_planet('./Figures/'+flight_id+'/VIS/GOES_vis_' + sat_time + '.png')




# %%

# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_vis(current_time_pd)
ax = plt.gca()
sat_time = sat_time[:-4]+'Z'

# Plot the flight path
#plot_path(path,ax=ax,color='orange')

ax.annotate(sat_time, (-12, 1), backgroundcolor="white")


box = [-35, -15, 0, 20]
ax.set_extent(box)



ax.set_position([0,0,1,1],which='both')

ax.annotate('IR: ' + sat_time, (-20, 1), backgroundcolor="white")

ax.annotate('Box: ' + str(box), (-34.5, 1), backgroundcolor="white")


fig.set_figwidth(10)
fig.set_figheight(10)
ax.set_aspect('auto')

export_planet('./Figures/'+flight_id+'/Planet/VIS_GOES_' + sat_time + '.png')


# %% [markdown]
# ### IR

# %%
# Use NASA world view to get the most recent GOES visible image and plot it

# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_ir(current_time_pd)
ax = plt.gca()

# Plot the flight path
plot_path(path,ax=ax,color='orange')

ax.annotate('IR: ' + sat_time, (-12, 1), backgroundcolor="white")

export_planet('./Figures/'+flight_id+'/IR/GOES_IR_' + sat_time + '.png')


# %% [markdown]
# ### Make an image that takes up the whole figure

# %%
# Use NASA world view to get the most recent GOES visible image and plot it

# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_ir(current_time_pd)
ax = plt.gca()



ax.gridlines(draw_labels=False, dms=True, x_inline=False, y_inline=False, alpha = 0.25)




box = [-35, -15, 0, 20]
ax.set_extent(box)



ax.set_position([0,0,1,1],which='both')

ax.annotate('IR: ' + sat_time, (-20, 1), backgroundcolor="white")

ax.annotate('Box: ' + str(box), (-34.5, 1), backgroundcolor="white")


fig.set_figwidth(10)
fig.set_figheight(10)
ax.set_aspect('auto')

export_planet('./Figures/'+flight_id+'/Planet/IR_GOES_' + sat_time + '.png')



# %%
#aa = ax.get_images()
#aa = aa[0]
#bb = aa.get_array()



# %% [markdown]
# ## Total column water vapour products

# %% [markdown]
# ### Download the TCWV from the ABI

# %%
current_time = datetime.utcnow()

try:
   
   print('downloading TPW data')
   # Get the latest TPW image
   g_TPW = goes_latest(satellite='goes16',product='ABI-L2-TPW', domain='F')

except:
   # Otherwise get something a bit older
   print("could not find latest TPW, trying to get file from 2 hours ago")
   time_sat = current_time - timedelta(hours=2)
   g_TPW = goes_nearesttime(time_sat, satellite=16, product="ABI-L2-TPW", domain = "F")


# %% [markdown]
# ### Visible and TPW

# %%
# Use NASA world view to get the most recent GOES visible image and plot it


# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_vis(current_time_pd)
ax = plt.gca()
sat_time = sat_time[:-4]+'Z'

# Plot the flight path
plot_path(path,ax=ax,color='orange')

ax.annotate('VIS: ' + sat_time, (-12, 1), backgroundcolor="white")


# No idea what this does
crs, x, y = abi_crs(g_TPW, 'TPW')

# Plot the Total column water vapor semi-transparently
c = ax.pcolormesh(x, y, g_TPW.TPW, transform=crs, cmap='tab20c', vmin=42,vmax=57,alpha=0.4)
cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"{g_TPW.TPW.long_name}\n({g_TPW.TPW.units})",ticks=[42,45,48,51,54,57])

# Some niceness for the plot
ax.set_extent([-50, 0, 0, 23])
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

ax.annotate('TPW: '+str(g_TPW.t.values.astype('datetime64[m]'))+'Z', (-48, 23), backgroundcolor="white",color="blue")

export_planet('./Figures/'+flight_id+'/VIS_and_TPW/GOES_vis_and_TPW_' + sat_time + '.png',dpi=200)



# %% [markdown]
# ### ABI TPW on its own

# %%
# Create the figure
projection = ccrs.PlateCarree()
plt.figure(figsize=(10, 5))

# Plot the flight path
ax = path_preview(path)
ax.set_global()
ax.coastlines()

# plot the water vapour field

# No idea what this does
crs, x, y = abi_crs(g_TPW, 'TPW')

# Plot the Total column water vapor semi-transparently
c = ax.pcolormesh(x, y, g_TPW.TPW, transform=crs, cmap='tab20c', vmin=42,vmax=57,alpha=0.4)
cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"{g_TPW.TPW.long_name}\n({g_TPW.TPW.units})",ticks=[42,45,48,51,54,57])

# Some niceness for the plot
ax.set_extent([-50, 0, 0, 20])
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

ax.annotate('TPW: '+str(g_TPW.t.values.astype('datetime64[m]'))+'Z', (-48, 23), backgroundcolor="white",color="blue")


export_planet('./Figures/'+flight_id+'/TPW/GOES_TPW_' + str(g_TPW.t.values.astype('datetime64[m]')) + '.png',dpi=200)

# %% [markdown]
# ### TCWV from daily AMRSU

# %%
current_day = datetime.today()
current_day_pd = pd.Timestamp(current_day)


fig,sat_time,goes_image = goes.current_satellite_image_wv_night(current_day_pd)


# %%
CWV = goes_image.values*(75/255)
CWV = CWV[0,:,:]
CWV = np.where(CWV==0,np.nan,CWV)


# Get the current time
current_time = datetime.utcnow()
current_time_pd = pd.Timestamp(current_time)

# Use the goes.py package to plot the satellite image
fig,sat_time = goes.current_satellite_image_vis(current_time_pd)
ax = plt.gca()
sat_time = sat_time[:-4]+'Z'

# Plot the flight path
plot_path(path,ax=ax,color='orange')

ax.annotate('VIS: ' + sat_time, (-12, 1), backgroundcolor="white")


# plot the water vapour field



# Plot the Total column water vapor semi-transparently
c = ax.pcolormesh(goes_image.x, goes_image.y, CWV, cmap='tab20c_r', vmin=30,vmax=60,alpha=0.3)
cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"column water vapour\n(mm)",ticks=[30,36,42,48,54,60])

# Some niceness for the plot
ax.set_extent([-50, 0, 0, 20])
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

#ax.annotate('TPW: '+str(g_TPW.t.values.astype('datetime64[m]'))+'Z', (-48, 23), backgroundcolor="white",color="blue")

export_planet('./Figures/'+flight_id+'/VIS_and_TPW/GOES_VIS_AMSRU_TPW_' + sat_time + '.png',dpi=200)



# %% [markdown]
# ### Column water vapour "MIMIC" from Microwave combined with Geostationary

# %%
# Try to get the column water vapour image

url_prefix = 'https://tropic.ssec.wisc.edu/real-time/mtpw2/webImages/tpw_nrl_colors/natl/'
fname_url = url_prefix+"file_of_filenames_24.txt"


contents = requests.get(fname_url).text.splitlines()

# Going a few hours back on the recommendation of Florian
image_name = contents[-2]

sat_date = image_name[-23:-15]
sat_time = image_name[-14:-12]+':'+image_name[-10:-8]


image_name = url_prefix+image_name
response = requests.get(image_name)
TPW_image = np.array(Image.open(BytesIO(response.content)))


# This is super dumb. Sorry Lukas.

col = np.sum(TPW_image[:,:,0:3],2)

# Find the indices of the non-zero elements
indices = np.nonzero(col[120,:]<255*3)

# The first and last indices will be the first and last True values
Xf = indices[0][0]
Xl = indices[0][-1]

# Find the indices of the non-zero elements
indices = np.nonzero(col[:,200]<255*3)

# The first and last indices will be the first and last True values
Yf = indices[0][0]
Yl = indices[0][-1]


TPW_image_cropped = TPW_image[Yf:Yl,Xf:Xl,:]

colbar = TPW_image_cropped[:,-10,:]
colbar = colbar[-2:2:-1,:]/255

col = np.sum(TPW_image_cropped[:,:,0:3],2)

# Find the indices of the non-zero elements
indices = np.nonzero(col[120,:]==255*3)

# The first and last indices will be the first and last True values
Xf = indices[0][0]


TPW_image_cropped = TPW_image_cropped[:,:Xf,:]

N = np.shape(TPW_image_cropped);

x = np.linspace(-110,10,N[1])
y = np.linspace(0,60,N[0])

TPW_matrix = np.flipud(TPW_image_cropped)

TPW_values = TPW_matrix[:,:,0]/255*75


plt.figure(figsize=(15,9))
plt.imshow(TPW_image)


# %%

# For some reason I don't know how to create a geoaxes - so using path_preview to do this
ax = path_preview(path)
plot_path(path,ax=ax,color='blue')

newcmp = mpl.colors.ListedColormap(colbar)

c = ax.pcolormesh(x, y, TPW_matrix, cmap=newcmp, vmin=0,vmax=75,alpha=1)
cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"column water vapour\n(mm)",ticks=[0,10,20,30,40,50,60,70])

ax.annotate('TPW: ' + sat_date + ' ' + sat_time , (-18, 3), backgroundcolor="white")

plt.savefig('./Figures/'+flight_id+'/TPW/MIMIC_TPW2_' + sat_date + ' ' + sat_time + 'Z.png',dpi=200)




# %%
# Calculate the TPW values from the CWV image in an approximate way

# Values of the TPW that correspond to the colors in the colorbar
cwv_values = np.linspace(0,75,len(colbar)).tolist()

# Create some matrices that we can subtract
TPWm = TPW_matrix[:,:,0:3]/255
colm = colbar[:,0:3]

TPWm = np.tile(TPWm,[len(colm),1,1,1])
TPWm = np.transpose(TPWm,[0,3,1,2])

colm = np.tile(colm,[1,1,1,1])
colm = np.transpose(colm,[2,3,0,1])

# Distance between the TPW color and the values in the colorbar
dist = np.sum((TPWm-colm)**2,1)

# Find the index of the colorbar closest to each color
I = dist.argmin(axis=0)

# Now go through the image matrix and calculate the actual cwv value
# This should not use a loop (sorry Lukas)
N = np.shape(I)
TWP_values = np.zeros(np.shape(I))
for i in range(N[0]-1):
   for j in range(N[1]-1):

      TPW_values[i,j] = cwv_values[I[i,j]]
    


# %%
x = np.linspace(-110,10,N[1])
y = np.linspace(0,60,N[0])

# Create the figure
projection = ccrs.PlateCarree()
plt.figure(figsize=(10, 5))

# Plot the flight path
ax = path_preview(path)
plot_path(path,ax=ax,color='blue')
ax.set_global()
ax.coastlines()

# plot the water vapour field

# Plot the Total column water vapor
c = ax.pcolormesh(x, y, TPW_values, cmap='tab20c', vmin=42,vmax=57,alpha=1)

cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"{'total column water'}\n({'mm'})",ticks=[42,45,48,51,54,57])

# Some niceness for the plot
ax.set_extent([-50, 0, 0, 20])
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

ax.annotate('TPW: ' + sat_date + ' ' + sat_time , (-12, 2), backgroundcolor="white")

export_planet('./Figures/'+flight_id+'/TPW/MIMIC_TPW2_tab' + sat_date + ' ' + sat_time + 'Z.png',dpi=200)



# %% [markdown]
# ### Download AOD data

# %%
try:
   print('downloading AOD data')
   # Get the latest AOD image
   g_AOD = goes_latest(satellite='goes16',product='ABI-L2-AOD', domain='F')

except:
   # Otherwise get something a bit older
   print("could not find latest AOD, trying to get file from 2 hours ago")
   time_sat = current_time - timedelta(hours=2)
   g_AOD = goes_nearesttime(time_sat, satellite=16, product="ABI-L2-AOD", domain = "F")



# %% [markdown]
# ### Aerosol optical depth

# %%
# Create the figure
projection = ccrs.PlateCarree()
plt.figure(figsize=(10, 5))

# Plot the flight path
ax = path_preview(path)
ax.set_global()
ax.coastlines()


# No idea what this does
crs, x, y = abi_crs(g_AOD, 'AOD')

# Plot the Total column water vapor semi-transparently
c = ax.pcolormesh(x, y, g_AOD.AOD, transform=crs, cmap='gist_ncar', vmin=0,vmax=3,alpha=1)
cc = plt.colorbar(c, ax=ax, shrink=.6, pad=.05, orientation='horizontal', label=f"{g_AOD.AOD.long_name}\n({g_AOD.AOD.units})",ticks=[0,0.25,0.5,0.75,1,1.25,1.5,1.75,2,2.25,2.5,2.75,3])

# Some niceness for the plot
ax.set_extent([-50, 0, 0, 20])
ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)

plt.title(g_AOD.t.values.astype('datetime64[m]'))

export_planet('./Figures/'+flight_id+'/AOD/GOES_AOD_' + str(g_AOD.t.values.astype('datetime64[m]')) + '.png',dpi=200)


# %% [markdown]
# ### Download the full ABI data
# This takes a long time, so commented out for now
# But it can give you snapshots of the "water vapur" estimate from a mixture of channels

# %%
# # Download the latest GOES information. This might take a long time
# try:
#    print('downloading ABI data')
#    # Get the latest visible image
#    g_visible = goes_latest(satellite='goes16',product='ABI',domain = 'F')

# except:
#    # Otherwise get something a bit older
#    print("could not find latest VIS, trying to get file from 2 hours ago")
#    time_sat = current_time - timedelta(hours=2)
#    g_visible = goes_nearesttime(time_sat, satellite=16, product="ABI", domain = "F")

# rgb_products = [i for i in dir(g_visible.rgb) if i[0].isupper()]
# rgb_products


# %%

# # Plot the flight path
# ax = path_preview(path)
# ax.set_global()
# ax.coastlines()


# # No idea what this does
# goes_kwargs = g_visible.rgb.imshow_kwargs

# RGB = getattr(g_visible.rgb, 'WaterVapor')()

# # Plot the GOES visible satelite image
# ax.imshow(RGB, transform = g_visible.rgb.crs, regrid_shape=3500, interpolation='nearest') 

# ax.set_extent([-50, 0, 0, 20])
# ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha = 0.25)


# ax.set_title(f"{g_visible.orbital_slot} {'WaterVapor'}", loc='left', fontweight='bold')
# ax.set_title(f"{g_visible.t.dt.strftime('%H:%M UTC %d-%b-%Y').item()}", loc="right")



# plt.savefig('../Figures/'+flight_id+'/WV/GOES_WV_' + str(g_visible.t.values.astype('datetime64[m]')) + '.png',dpi=200)


