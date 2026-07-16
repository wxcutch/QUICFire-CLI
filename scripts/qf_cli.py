import json
import yaml
import fastfuels_sdk as ff
import quicfire_tools as qft
from pathlib import Path
import sys, os
import copy
import struct
import numpy as np
import matplotlib.pyplot as plt
import psutil

required_vars = {'simulation': ['saveLocation', 'duration'],
                 'domain' : ["mode"],
                 'fuels' : ["mode"],
                 'weather' : ['windSpeed', 'windDirection'], 
                 'ignition' : ['mode']
                 }

required_for_mode = {"domain" : {
    "idealized" : ["nx", "ny", "nz"]
}}

default_vars = {'simulation' : {
                    'saveOutputVariables' : ['Winds', 'Energy'],
                    "nProc" : 1,
                    'saveOutputFrequency' : 300,
                },
                'domain' : {
                    'horizontalGridSize' : 2, 
                    'verticalGridSize' : 1,
                    'gisProjection' : "EPSG:4326"
                },
                'fuels' : {},
                'weather' : {'obHeight' : 6},
                'ignition' : {'mode':'gis', 'timing':'instant', 'width':2, 'startTime' : 1}}

required_namelist_sections = ['simulation', 'domain', 'fuels', 'weather', 'ignition']

FASTFUELS_DTYPE_SIZE_BYTES = 4
ff_files = ['topo.dat', 'treesfueldepth.dat', 'treesmoist.dat', 'treesrhof.dat', 'metadata.json', 'domain.geojson']
ff_fancy_names = {'topo.dat' : 'Topography [m ASL]', 'treesfueldepth.dat' : "Surface Fuel Depth [m]", 
                  'treesmoist.dat' : "Fuel Moisture [g H2O / g Fuel]", 'treesrhof.dat' : r"Fuel Bulk Density [$kg\ m^{-3}$]"}

def load_qft_inputs_outputs(namelist):
    member_loc = namelist['simulation']['saveLocation']
    inputs = qft.SimulationInputs.from_directory(member_loc)
    outputs = qft.SimulationOutputs.from_simulation_inputs(member_loc / 'Output', inputs)
    return inputs, outputs

def check_namelist_requirements_and_fill_defaults(namelist, quiet=False):
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
            elif(requested_output_var != 'Winds' and requested_output_var != "Energy" and quiet==False):
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
        
    # for section_with_req in required_vars.keys():
    #     for req_var in required_vars[section_with_req]:
    #         if (req_var not in namelist[section_with_req].keys()):
    #             print(f"ERROR: missing required variable {req_var} in section {section_with_req} of the namelist")
    #             final_namelist = None

    if (final_namelist == None):
        return None

    final_namelist['simulation']['saveLocation'] = Path(namelist['simulation']['saveLocation'])
    for section in default_vars.keys():
        for varname in default_vars[section].keys():
            if(varname not in namelist[section].keys()):
                final_namelist[section][varname] = default_vars[section][varname]
                if(quiet == False):
                    print(f"WARNING: setting {varname} in {section} to default value: {default_vars[section][varname]}")
    
    if(namelist['domain']['mode'] != "idealized" and not os.path.isfile(namelist['domain']['gis'])):
        print(f"WARNING: failed to find the gis file from a global path, checking with save location")
        if(not os.path.isfile(final_namelist['simulation']['saveLocation'] / namelist['domain']['gis'])):
            print(f"ERROR: couldn't find gis file {final_namelist['simulation']['saveLocation'] / namelist['domain']['gis']}")
            raise FileNotFoundError
        else:
            final_namelist['domain']['gis'] = final_namelist['simulation']['saveLocation'] / namelist['domain']['gis']
    final_namelist['simulation']['outputs'] = _handle_output_vars(final_namelist['simulation']['saveOutputVariables'])

    if('maxParallelExecute' not in final_namelist['simulation']):
        n_cores = psutil.cpu_count(logical=False)
        n_members = int((n_cores - 2) / final_namelist['simulation']['nProc'])
        if(quiet == False):
            print(f"WARNING: the maximum number of members to execute was not specified. Detected {n_cores} physical cores on your device, I will leave 2 for background process execution. Given that you requested {final_namelist['simulation']['nProc']} threads per member, maximum number of members to execute simultaneously was set to {n_members}. Please watch your memory as this executes, if you exceed your memory allocation there may be considerable slowdowns in execution time.")
    return final_namelist

def load_cli_namelist(allow_multiple_files=False, from_file=None):
    raw_file = from_file
    if(from_file == None):
        options = sys.argv[1:]
        if(len(options) != 1 and allow_multiple_files != True):
            print("ERROR: Please specify the simulation yaml namelist after the command") 
            exit()
        raw_file = options[0]

    with open(raw_file, 'r') as raw_namelist:
        namelist = yaml.load(raw_namelist, Loader=yaml.FullLoader)
    
    namelist = check_namelist_requirements_and_fill_defaults(namelist)
    return namelist

def all_ff_present(folder):
    all_ff_present = True
    folder_contents = os.listdir(folder)
    for file in ff_files:
        if(file not in folder_contents):
            all_ff_present = False
            print(f"WARNING: {file} is missing from your input files at {folder}")
    return all_ff_present    

def plot_field(namelist, field, vmin=None, vmax=None, cmap="Greens", cbar_label=None, saveas="", size_base=6, transpose=True):
    nx, ny, _ = get_nx_ny_nz(namelist)

    x_axis = np.arange(nx) * namelist['domain']['horizontalGridSize']
    y_axis = np.arange(ny) * namelist['domain']['horizontalGridSize']
    fig, ax = plt.subplots(1, 1, subplot_kw={'aspect':'equal'}, figsize=(size_base, size_base * (float(ny / nx) - 0.1)))

    if(transpose == True):
        grid_mesh = ax.pcolormesh(x_axis, y_axis, field.T, cmap=plt.get_cmap(cmap), vmin=vmin, vmax=vmax)    
    else:
        try:
            grid_mesh = ax.pcolormesh(x_axis, y_axis, field, cmap = plt.get_cmap(cmap), vmin=vmin, vmax=vmax)
        except TypeError:
            print("WARNING: Had to transpose the grid without being told to because array sizes were not correct")
            grid_mesh = ax.pcolormesh(x_axis, y_axis, field.T, cmap=plt.get_cmap(cmap), vmin=vmin, vmax=vmax)
 
    plt.colorbar(grid_mesh, label=cbar_label)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")

    plt.tight_layout()
    plt.savefig(saveas)

def get_grid_from_raw_dat(namelist, file):
    nx, ny, nz = get_nx_ny_nz(namelist)
    floc = file if os.path.exists(file) else namelist['simulation']['saveLocation'] / file
    
    fsize = os.path.getsize(floc)
    is_2d = int(fsize / (nx * ny)) == FASTFUELS_DTYPE_SIZE_BYTES
    grid_nz = 1 if is_2d == True else nz
    
    with open(floc, 'rb') as fstream:
        pre1 = struct.unpack('i', fstream.read(4))[0]
        grid = np.frombuffer(fstream.read(nx * ny * grid_nz * FASTFUELS_DTYPE_SIZE_BYTES), 'f').reshape((nx, ny, grid_nz), order='F')
    return grid

def get_nx_ny_nz(namelist):
    if(os.path.isfile(namelist['simulation']['saveLocation'] / 'metadata.json')):
        with open(namelist['simulation']['saveLocation'] / 'metadata.json') as raw_meta:
            ff_meta = json.load(raw_meta)
        nx = ff_meta['nx']
        ny = ff_meta['ny']
        nz = ff_meta['nz']
    else:
        nx = namelist['domain']['nx']
        ny = namelist['domain']['ny']
        nz = namelist['domain']['nz']
    return nx, ny, nz

def find_ignitions(namelist, input_file):
    nx, ny, nz = get_nx_ny_nz(namelist)
    ignite_mask = np.zeros((nx, ny, 1))
    
    try:
        with open(input_file, 'r') as buffer:
            ignition_file_lines = buffer.readlines()
    except FileNotFoundError:
        with open(namelist['simulation']['saveLocation'] / input_file, 'r') as buffer:
            ignition_file_lines = buffer.readlines()

    ignitions = ignition_file_lines[6:] #throwing out the header
    if(len(ignitions) < 1):
        return ignite_mask
    
    for line in ignitions:
        ignite_x, ignite_y, t = str.split(line)
        ignite_mask[int(ignite_x) - 1, int(ignite_y) - 1, :] = 1
    return ignite_mask