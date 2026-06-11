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

required_vars = {'simulation': ['saveLocation', 'duration'],
                 'domain' : ["gis", "gisProjection"],
                 'fuels' : ['apiKey'],
                 'weather' : ['windSpeed', 'windDirection'], 
                 }

default_vars = {'simulation' : {
                    'saveOutputVariables' : ['Winds', 'Energy'],
                    "nProc" : 1,
                    'saveOutputFrequency' : 300
                },
                'domain' : {
                    'horizontalGridSize' : 2, 
                    'verticalGridSize' : 1,
                    'gisProjection' : "EPSG:4326"
                },
                'fuels' : {},
                'weather' : {'obHeight' : 6},
                'ignition' : {'mode':'gis', 'timing':'instant', 'width':10, 'startTime' : 1}}

required_namelist_sections = ['simulation', 'domain', 'fuels', 'weather', 'ignition']

def _main():
    namelist = load_cli_namelist()
    
    namelist = check_namelist_requirements_and_fill_defaults(namelist)
    if(namelist == None):
        exit()

    if not os.path.isdir(namelist['simulation']['saveLocation']):
        os.mkdir(namelist['simulation']['saveLocation'])

    create_fuels(namelist)
    write_ignition(namelist)
    write_qf_inputs(namelist)
    print("simulation setup complete!")

def load_cli_namelist():
    options = sys.argv[1:]
    if(len(options) != 1):
        print("ERROR: Please specify the simulation json namelist after the command") 
        exit()

    with open(options[0], 'r') as raw_namelist:
        namelist = json.load(raw_namelist)

    namelist['simulation']['saveLocation'] = Path(namelist['simulation']['saveLocation'])
    return namelist

def create_fuels(namelist):
    ff.api.set_api_key(namelist['fuels']['apiKey'])
    with open(namelist['domain']['gis']) as raw_gis:
        gis_info = json.load(raw_gis)
    
    burn_unit = next(
        feature for feature in gis_info['features'] if (str.lower(feature['properties']['name']) == "burnunit" or str.lower(feature['properties']['name']) == "burn_unit")
    )

    polygon = sp.Polygon(burn_unit['geometry']['coordinates'])
    roi = gpd.GeoDataFrame(geometry=[polygon], crs=namelist['domain']['gisProjection'])

    available_fuels_options = namelist['fuels'].keys()
    print(namelist['fuels'])
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
    else:
        print("ERROR: only supported ignition specification is a LineString in your .geojson file defining your domain. Your ignite.dat file will be missing")

def get_nx_ny_nz(namelist):
    with open(namelist['simulation']['saveLocation'] / 'metadata.json') as raw_meta:
        ff_meta = json.load(raw_meta)
    return ff_meta['nx'], ff_meta['ny'], ff_meta['nz']

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
    simulation.runtime_advanced_user_inputs.num_cpus = namelist['simulation']['nProc']
    simulation.set_output_interval(namelist['simulation']['saveOutputFrequency'])
    simulation.write_inputs(namelist['simulation']['saveLocation'])
     
def check_namelist_requirements_and_fill_defaults(namelist):
    global required_vars, required_namelist_sections, default_vars

    def _handle_output_vars(varlist):
        #handle output variables
        qf_outputs = {
                    'eng_to_atm':False, 
                    'react_rate':False,
                    'fuel_dens':False,
                    'qf_wind':False,
                    'qu_wind_inst':False,
                    'qu_wind_avg':False,
                    'fuel_moist':False,
                    'mass_burnt':False,
                    'emissions':False,
                    'radiation':False,
                    'surf_eng':False
                    }
        
        for requested_output_var in varlist:
            if(requested_output_var in qf_outputs.keys()):
                qf_outputs[requested_output_var] = True
            elif(requested_output_var != 'Winds' and requested_output_var != "Energy"):
                print(f"WARNING: Did not recognize requested output variable {requested_output_var}")
        
        if('Winds' in varlist):
            qf_outputs['qu_wind_avg'] = True
        if("Energy" in varlist):
            qf_outputs['surf_eng'] = True
            qf_outputs['eng_to_atm'] = True
            qf_outputs['radiation'] = True 

        return qf_outputs
    
    final_namelist = copy.deepcopy(namelist)

    for required_section in required_namelist_sections:
        if(required_section not in namelist.keys()):
            print(f"ERROR: Missing required namelist section {required_section}")
            final_namelist = None
        
    for section_with_req in required_vars.keys():
        for req_var in required_vars[section_with_req]:
            if (req_var not in namelist[section_with_req].keys()):
                print(f"ERROR: missing required variable {req_var} in section {section_with_req} of the namelist")
                final_namelist = None

    if (final_namelist == None):
        return None

    final_namelist['simulation']['saveLocation'] = Path(namelist['simulation']['saveLocation'])

    for section in default_vars.keys():
        for varname in default_vars[section].keys():
            if(varname not in namelist[section].keys()):
                final_namelist[section][varname] = default_vars[section][varname]
                print(f"WARNING: setting {varname} in {section} to default value: {default_vars[section][varname]}")
    
    final_namelist['simulation']['outputs'] = _handle_output_vars(namelist['simulation']['saveOutputVariables'])
    return final_namelist

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

def _ignitions_from_topography(namelist, nx, ny):
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
        print(ignition_pattern.shape)

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