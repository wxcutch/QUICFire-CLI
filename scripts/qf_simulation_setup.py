import os, sys
import geopandas as gpd
import shapely as sp 
import json
from pathlib import Path
import fastfuels_sdk as ff
import quicfire_tools as qft
import copy
import numpy as np
import struct
import math
from qf_cli import *

def _main():
    namelist = load_cli_namelist()
    if(namelist == None):
        exit()

    if not os.path.isdir(namelist['simulation']['saveLocation']):
        os.mkdir(namelist['simulation']['saveLocation'])

    create_fuels(namelist)
    write_qf_inputs(namelist)
    write_ignition(namelist)
    print("simulation setup complete!")

def create_fuels(namelist):
    ff.api.set_api_key(namelist['fuels']['apiKey'])
    try:
        with open(namelist['domain']['gis']) as raw_gis:
            gis_info = json.load(raw_gis)
    except FileNotFoundError: 
        with open(namelist['simulation']['saveLocation'] / namelist['domain']['gis']) as raw_gis:
            gis_info = json.load(raw_gis)

    burn_unit = next(
        feature for feature in gis_info['features'] if (str.lower(feature['properties']['name']) == "burnunit" or str.lower(feature['properties']['name']) == "burn_unit")
    )

    try:
        polygon = sp.Polygon(burn_unit['geometry']['coordinates'])
    except TypeError:
        polygon = sp.Polygon(burn_unit['geometry']['coordinates'][0])
    roi = gpd.GeoDataFrame(geometry=[polygon], crs=namelist['domain']['gisProjection'])

    available_fuels_options = namelist['fuels'].keys()
    
    ff.export_roi(roi = roi, export_path = namelist['simulation']['saveLocation'] / 'qf_fastfuels.zip', verbose=True, export_format="QUIC-Fire",
                    topography_config= None if "topographyConfig" not in available_fuels_options else namelist['fuels']['topographyConfig'],
                    surface_config= None if "surfaceConfig" not in available_fuels_options else namelist['fuels']['surfaceConfig'],
                    tree_cong= None if "treeConfig" not in available_fuels_options else namelist['fuels']['treeConfig'],
                    features_config= None if "featuresConfig" not in available_fuels_options else namelist['fuels']['featuresConfig'],
                    tree_inventory_config= None if "treeInventoryConfig" not in available_fuels_options else namelist['fuels']['treeInventoryConfig'],
                  )
    from zipfile import ZipFile
    with ZipFile(namelist['simulation']['saveLocation'] / 'qf_fastfuels.zip', 'r') as zObject:
        zObject.extractall(path=namelist['simulation']['saveLocation'])

def write_ignition(namelist):
    if(namelist['ignition']['mode'] == 'gis'):
        ignitions, timing = _ignitions_from_gis(namelist)
        _write_ignition_file(ignitions, timing, namelist['simulation']['saveLocation'])
    elif(namelist['igntion']['mode'] == 'topography'):
        ignitions, timing = _ignitions_from_topography(namelist)
        _write_ignition_file(ignitions, timing, namelist['simulation']['saveLocation'])
    elif(namelist['ignition']['mode'] == 'rectangle'):
        _rectangle_ignition(namelist)
    else:
        print("ERROR: only supported ignition specification is a LineString in your .geojson file defining your domain. Your ignite.dat file will be missing")

def write_qf_inputs(namelist):
    #figure out the size of the grid based on the domain GIS
    nx, ny, nz = get_nx_ny_nz(namelist)
    simulation = qft.SimulationInputs.create_simulation(nx=nx, ny=ny,
                                                        fire_nz=nz,
                                                        wind_speed=namelist['weather']['windSpeed'],
                                                        wind_direction=namelist['weather']['windDirection'],
                                                        simulation_time=namelist['simulation']['duration'])
    simulation.set_output_files(**namelist['simulation']['outputs'])
    simulation.set_custom_simulation()
    _set_atmos_grid_height(namelist, simulation)
    simulation.runtime_advanced_user_inputs.num_cpus = namelist['simulation']['nProc']
    simulation.set_output_interval(namelist['simulation']['saveOutputFrequency'])
    simulation.write_inputs(namelist['simulation']['saveLocation'])

def _set_atmos_grid_height(namelist, simulation):
    #check to see if the user went ahead and specified 
    if('atmosDepth' in namelist['domain'].keys()):
        simulation.qu_simparams.quic_domain_height = namelist['domain']['atmosDepth']
        return
    
    topo_grid = get_grid_from_raw_dat(namelist, 'topo.dat')
    highest_point = np.nanmax(topo_grid)
    lowest_point = np.nanmin(topo_grid)

    change = highest_point - lowest_point
    if(change > 50):
        print(f"Big terrain height difference, changing the atmosphere domain height to {change * 3.25}")
        simulation.qu_simparams.quic_domain_height = change * 3.25
    else:
        print("Using quicfire-tools default vertical grid")

def _rectangle_ignition(namelist):
    #reopen the qft class
    simulation = qft.SimulationInputs.from_directory(namelist['simulation']['saveLocation'])
    simulation.set_rectangle_ignition(namelist['ignition']['xMin'], namelist['ignition']['yMin'], namelist['ignition']['xLength'], namelist['ignition']['yLength'])
    simulation.write_inputs(namelist['simulation']['saveLocation'])

def _write_ignition_file(locations, timing, save_loc):
    ignition_locations = np.where(locations)
    ignition_times = timing[ignition_locations]
    nlocs = len(ignition_locations[0])

    ignition_file_lines = [
        'igntype=4\n',
        '&aeriallist\n',
        f'naerial={nlocs}\n',
        f'targettemp=1000.00\n', #vestigial
        f'ramprate=172.00\n', #vestigial
        '/\n'
    ]
    for loc in range(nlocs):
        ignition_file_lines.append(f' {ignition_locations[0][loc]+1} {ignition_locations[1][loc]+1} {ignition_times[loc]:0.2f} \n')
    with open(save_loc / 'ignite.dat', 'w') as ignition_file:
        ignition_file.writelines(ignition_file_lines)

def _ignitions_from_topography(namelist):
    nx, ny, nz = get_nx_ny_nz(namelist)
    if(not os.path.exists(namelist['simulation']['saveLocation'] / 'topo.dat')):
        raise FileNotFoundError("Couldn't find the topography file to use while writing ignitions")

    with open(namelist['simulation']['saveLocation'] / 'topo.dat', 'rb') as f:
        pre1 = struct.unpack("i", f.read(4))[0]
        topo = np.frombuffer(f.read(nx * ny * 4), 'f').reshape((nx, ny), order='F')
    
    bottom = namelist['ignition']['bottomElevation']
    top = namelist['ignition']['topElevation']

    ignition_mask = (topo >= bottom) & (topo <= top)
    ignition_locations = np.where(ignition_mask)
    timing = np.full(topo.shape, namelist['ignition']['startTime'])
    _write_ignition_file(ignition_locations, timing, namelist['saveLocation'])

def _ignitions_from_gis(namelist, feature_key='ignition'):
    from pyproj import Transformer

    def _snap_to_grid(x, y, origin_x, origin_y, domain_x_size, domain_y_size):
        i = round((x - origin_x) / domain_x_size)
        j = round((y - origin_y) / domain_y_size)
        snapped_x = origin_x + i * domain_x_size
        snapped_y = origin_y + i * domain_y_size
        return i, j, snapped_x, snapped_y
    def _diagonal_line_ignition(existing_ignition_pattern, start_x, start_y, end_x, end_y, thickness=1):
        print('Running diagonal line ignition')
        ignition_pattern = np.copy(existing_ignition_pattern)

        dx = end_x - start_x
        dy = end_y - start_y

        if(dy == 0):
            ignition_pattern[start_x - int(thickness / 2):end_x + math.ceil(thickness / 2), start_y - int(thickness / 2) : start_y + math.ceil(thickness/2)] = 1
            return ignition_pattern

        slope = float(dy) / dx

        ignite_y = start_y
        ignite_x = float(start_x)
        while(ignite_y <= end_y):
            if(slope > 1):
                end_x = int(ignite_x + slope) + math.ceil(thickness / 2) - 1
            else:
                end_x = int(ignite_x) + math.ceil(thickness/2)
            ignition_pattern[int(ignite_x - int(thickness/2)) : end_x, 
                            int(ignite_y - int(thickness /2)) : int(ignite_y + math.ceil(thickness /2))] = 1
            ignite_y += 1
            ignite_x += slope
        
        return ignition_pattern
    simulation_folder = namelist['simulation']['saveLocation']

    with open(namelist['domain']['gis'], 'r') as raw_gis:
        gis_info = json.load(raw_gis)
    
    with open(simulation_folder / 'domain.geojson', 'r') as fastfuels_domain_response:
        ff_gis = json.load(fastfuels_domain_response)

    ignition_feature = next(
        f for f in gis_info['features'] if (str.lower(f['properties']['name']) == feature_key)
    )

    ff_domain = next(
        f for f in ff_gis['features'] if f['properties']['name'] == "domain"
    )

    if(ignition_feature['geometry']['type'] != "LineString"):
        print("ERROR: Only LineStrings are supported for GIS based ignitions at this time")
        return
    
    line_coords = ignition_feature['geometry']['coordinates']
    n_segments = len(line_coords) - 1
  
    ff_crs = ff_gis['crs']['properties']['name']
    user_crs = namelist['domain']['gisProjection']

    ff_origin_x, ff_origin_y = ff_domain['geometry']['coordinates'][0][0]

    nx, ny, nz = get_nx_ny_nz(namelist)

    transformer = Transformer.from_crs(user_crs, ff_crs, always_xy=True)
    ignition_line_projected = [transformer.transform(lon, lat) for lon, lat in line_coords]

    gridded_line_coords = []
    for x, y in ignition_line_projected:
        i, j, sx, sy = _snap_to_grid(x, y, ff_origin_x, ff_origin_y, namelist['domain']['horizontalGridSize'], namelist['domain']['horizontalGridSize'])
        gridded_line_coords.append([i, j])
    
    n_segments = len(gridded_line_coords) - 1
    ignitions = np.zeros((nx, ny))
    for s in range(n_segments):
        ignitions = _diagonal_line_ignition(ignitions, gridded_line_coords[s][0], gridded_line_coords[s][1], gridded_line_coords[s+1][0], gridded_line_coords[s+1][1], 
                                            thickness =1 if 'width' not in namelist['ignition'] else namelist['ignition']['width'])

    if(str.lower(namelist['ignition']['timing']) == "instant"):
        timing = np.full(ignitions.shape, namelist['ignition']['startTime'])

    return ignitions, timing

if __name__ == "__main__":
    _main()
