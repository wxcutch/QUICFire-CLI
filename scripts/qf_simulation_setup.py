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
import shutil
from qf_cli import *

quiet = False

def _main():
    global quiet
    namelist = load_cli_namelist()
    if(namelist == None):
        exit()

    if not os.path.isdir(namelist['simulation']['saveLocation']):
        os.mkdir(namelist['simulation']['saveLocation'])

    if('ensemble' not in namelist.keys()):
        quiet = True
        create_fuels(namelist)
        write_qf_inputs(namelist)
        write_ignition(namelist)
    else:
        print("Ensemble mode detected, will use saveLocation as root for members")   
        ensemble_setup(namelist)     

    print("simulation setup complete!")

def ensemble_setup(namelist):
    
    def get_path_and_values(branch, established_path=[]):
        #tunnel down to the established path
        setting_trees = []
        if(type(branch) == dict):
            #we have to keep going deeper
            for key in branch.keys():
                new_path = copy.deepcopy(established_path) + [key]
                children = get_path_and_values(branch[key], new_path)
                if(len(children) > 0):
                    setting_trees.append(children)
        else:
            if(type(branch) == list):
                for ensemble_value in branch:
                    setting_trees.append((ensemble_value, established_path))
        return setting_trees
        
    def plant_namelist_value(namelist, path, value):
        final_namelist = copy.deepcopy(namelist)
        working_namelist = final_namelist
        path_depth = 0
        while(path_depth < len(path) - 1):
            if(path[path_depth] not in working_namelist):
                working_namelist[path[path_depth]] = {}
            working_namelist = working_namelist[path[path_depth]]
            path_depth += 1

        working_namelist[path[-1]] = value
        return final_namelist
    
    def get_last_lists(sparse_list, dtype=tuple):
        last_lists = []
        if(type(sparse_list[0][0]) == dtype):
            return sparse_list
        for branch in range(len(sparse_list)):
            last_lists += get_last_lists(sparse_list[branch], dtype=dtype)
        return last_lists
    
    def find_existing_fastfuels_path(mem_namelist, completed_namelists):
        for nml in completed_namelists:
            other_nml = load_cli_namelist(from_file=nml)
            if(mem_namelist['fuels'] == other_nml['fuels']):
                return other_nml['simulation']['saveLocation']
        return None

    def generate_namelists(base_namelist, variable_splits, case_name_root="iter", n_random=1):
        base_namelist = copy.deepcopy(base_namelist)
        if('ensemble' in base_namelist.keys()):
            base_namelist.pop('ensemble')
        field_name = list(variable_splits.keys())[0]
        remaining_variables = copy.deepcopy(variable_splits)
        remaining_variables.pop(field_name)
        for case in variable_splits[field_name]:
            value, setting_path = case
            namelist = plant_namelist_value(base_namelist, setting_path, value)
            case_name = case_name_root + f"_{field_name}{value:03}"
            if(len(remaining_variables.keys()) > 0):
                generate_namelists(namelist, remaining_variables, case_name_root=case_name, n_random=n_random)
            else:
                if(n_random > 1):
                    for i in range(n_random):
                        random_seed_member_name = case_name + f"_mem{i+1:03}"
                        member_folder = Path(base_namelist['simulation']['saveLocation'] / random_seed_member_name)
                        print(f"Creating member at {str(member_folder)}")
                        namelist = plant_namelist_value(namelist, ['simulation', 'plumeRandomSeed'], i+5)
                        namelist = plant_namelist_value(namelist, ['simulation', 'saveLocation'], str(member_folder))
                        if not os.path.isdir(member_folder):
                            os.mkdir(member_folder)
                        
                        with open(member_folder / 'namelist.yml', 'w') as outfile:
                            yaml.dump(namelist, outfile) 
                else:
                    member_folder = Path(base_namelist['simulation']['saveLocation'] / case_name)
                    print(f"Creating member at {str(member_folder)}")
                    namelist = plant_namelist_value(namelist, ['simulation', 'saveLocation'], str(member_folder))
                    if not os.path.isdir(member_folder):
                        os.mkdir(member_folder)
                    with open(member_folder / 'namelist.yml', 'w') as outfile:
                        yaml.dump(namelist, outfile) 
    ensemble_namelist = namelist['ensemble']
    deg_of_freedom = get_path_and_values(ensemble_namelist)
    var_splits = get_last_lists(deg_of_freedom)
    named_splits = {}
    for var_set in var_splits:
        title = f"{var_set[0][1][-2]}-{var_set[0][1][-1]}"
        named_splits[title] = var_set

    generate_namelists(base_namelist=namelist, variable_splits=named_splits, n_random = ensemble_namelist['randomSeedMembers'])
    members = os.listdir(namelist['simulation']['saveLocation'])
    members.sort()
    completed_namelists = []
    for member in members:
        if(os.path.isdir(member)):
            mem_namelist_loc = Path(namelist['simulation']['saveLocation'] / member) / 'namelist.yml'
            print(mem_namelist_loc)
            with open(mem_namelist_loc, 'r') as buffer:
                mem_namelist = yaml.load(buffer, Loader=yaml.FullLoader)
            mem_namelist = check_namelist_requirements_and_fill_defaults(mem_namelist, quiet=True)
            if(namelist['fuels']['mode'] == 'fastfuels'):
                ff_path = find_existing_fastfuels_path(mem_namelist, completed_namelists)
                if(ff_path == None):
                    create_fuels(mem_namelist)
                else:
                    print(f'Copying FastFuels from {ff_path}')
                    for ff_file in ff_files:
                        shutil.copy(ff_path / ff_file, Path(namelist['simulation']['saveLocation'] / member) / ff_file)

            write_qf_inputs(mem_namelist)
            write_ignition(mem_namelist)
            completed_namelists.append(mem_namelist_loc)

def create_fuels(namelist):
    if(str.lower(namelist['fuels']['mode']) == 'fastfuels'):
        create_fastfuels(namelist)
    else:
        print('Will create uniform fuels in the QF input file creation step')


def create_fastfuels(namelist):
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
                    tree_config= None if "treeConfig" not in available_fuels_options else namelist['fuels']['treeConfig'],
                    features_config= None if "featuresConfig" not in available_fuels_options else namelist['fuels']['featuresConfig'],
                    tree_inventory_config= None if "treeInventoryConfig" not in available_fuels_options else namelist['fuels']['treeInventoryConfig'],
                  )
    from zipfile import ZipFile
    with ZipFile(namelist['simulation']['saveLocation'] / 'qf_fastfuels.zip', 'r') as zObject:
        zObject.extractall(path=namelist['simulation']['saveLocation'])

def write_ignition(namelist):
    if(namelist['ignition']['mode'] == 'gis'):
        ignitions_key = namelist['ignition']['name'] if 'name' in namelist['ignition'].keys() else "ignition"
        ignitions, timing = _ignitions_from_gis(namelist, feature_key=ignitions_key)
        _write_ignition_file(ignitions, timing, namelist['simulation']['saveLocation'])
    elif(namelist['ignition']['mode'] == 'topography'):
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
    if(str.lower(namelist['fuels']['mode']) == "idealized"):
        simulation.set_uniform_fuels(fuel_density = namelist['fuels']['fuelDensity'], 
                                     fuel_moisture = namelist['fuels']['fuelMoisture'],
                                     fuel_height= namelist['fuels']['fuelHeight'])
    else:
        simulation.set_custom_simulation(interpolate=True)
    _set_atmos_grid_height(namelist, simulation)
    simulation.runtime_advanced_user_inputs.num_cpus = namelist['simulation']['nProc']
    simulation.set_output_interval(namelist['simulation']['saveOutputFrequency'])
    simulation.write_inputs(namelist['simulation']['saveLocation'])
    if('plumeRandomSeed' in namelist['simulation']):
        simulation.quic_fire.random_seed = namelist['simulation']['plumeRandomSeed']

def _set_atmos_grid_height(namelist, simulation):
    global quiet
    #check to see if the user went ahead and specified 
    if('atmosDepth' in namelist['domain'].keys()):
        simulation.qu_simparams.quic_domain_height = namelist['domain']['atmosDepth']
        return
    
    if(os.path.isfile(namelist['simulation']['saveLocation'] / 'topo.dat')):
        topo_grid = get_grid_from_raw_dat(namelist, 'topo.dat')
        highest_point = np.nanmax(topo_grid)
        lowest_point = np.nanmin(topo_grid)

        change = highest_point - lowest_point
        if(change > 50):
            if(quiet == False):
                print(f"Big terrain height difference, changing the atmosphere domain height to {change * 3.25}")
            simulation.qu_simparams.quic_domain_height = change * 3.25
        else:
            if(quiet == False):
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
    global quiet
    from pyproj import Transformer

    def _snap_to_grid(x, y, origin_x, origin_y, domain_x_size, domain_y_size):
        i = round((x - origin_x) / domain_x_size)
        j = round((y - origin_y) / domain_y_size)
        snapped_x = origin_x + i * domain_x_size
        snapped_y = origin_y + i * domain_y_size
        return i, j, snapped_x, snapped_y
    def _diagonal_line_ignition(existing_ignition_pattern, start_x, start_y, end_x, end_y, thickness=1):
        if(quiet == False):
            print(f'Igniting from ({start_x}, {start_y}) to ({end_x}, {end_y})')
        ignition_pattern = np.copy(existing_ignition_pattern)

        dx = end_x - start_x
        dy = end_y - start_y

        if(dy == 0):
            ignition_pattern[start_x - int(thickness / 2):end_x + math.ceil(thickness / 2), start_y - int(thickness / 2) : start_y + math.ceil(thickness/2)] = 1
            return ignition_pattern

        slope = abs(dx / float(dy))        
        dy = 1 if(end_y > start_y) else -1

        ignite_y = start_y
        ignite_x = float(start_x)
        while(abs(ignite_y - end_y) > 1):
            if(slope > 1):
                end_x = int(ignite_x + slope) + math.ceil(thickness / 2) - 1
            else:
                end_x = int(ignite_x) + math.ceil(thickness/2)
            ignition_pattern[int(ignite_x - int(thickness/2)) : end_x, 
                            int(ignite_y - int(thickness /2)) : int(ignite_y + math.ceil(thickness /2))] = 1
            ignite_y += dy
            ignite_x += slope
        
        return ignition_pattern
    simulation_folder = namelist['simulation']['saveLocation']

    with open(namelist['domain']['gis'], 'r') as raw_gis:
        gis_info = json.load(raw_gis)
    
    with open(simulation_folder / 'domain.geojson', 'r') as fastfuels_domain_response:
        ff_gis = json.load(fastfuels_domain_response)
    print(f'looking for ignition feature {feature_key}')
    ignition_feature = next(
        f for f in gis_info['features'] if (str.lower(f['properties']['name']) == str.lower(feature_key))
    )

    if(quiet == False):
        print(f'found ignition feature {ignition_feature}')

    ff_domain = next(
        f for f in ff_gis['features'] if f['properties']['name'] == "domain"
    )

    if(ignition_feature['geometry']['type'] != "LineString"):
        print("ERROR: Only LineStrings are supported for GIS based ignitions at this time")
        return
    
    line_coords = ignition_feature['geometry']['coordinates']
    n_segments = len(line_coords) - 1

    if(quiet == False):
        print(f"Found {n_segments} segments to ignite in the input file")

    ff_crs = ff_gis['crs']['properties']['name']
    user_crs = namelist['domain']['gisProjection']

    ff_origin_x, ff_origin_y = ff_domain['geometry']['coordinates'][0][0]

    if(quiet == False):
        print(f"The origin of the fastfuels gis file is ({ff_origin_x}, {ff_origin_y})")

    nx, ny, nz = get_nx_ny_nz(namelist)

    if(quiet == False):
        print(f"Domain is nx: {nx}, ny: {ny} with a grid size of {namelist['domain']['horizontalGridSize']}")

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
