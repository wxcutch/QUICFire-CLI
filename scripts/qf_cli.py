import json
import yaml
import fastfuels_sdk as ff
import quicfire_tools as qft
from pathlib import Path
import sys, os
import copy
import struct
import numpy as np

required_vars = {'simulation': ['saveLocation', 'duration'],
                 'domain' : ["gis"],
                 'fuels' : ['apiKey'],
                 'weather' : ['windSpeed', 'windDirection'], 
                 'ignition' : ['mode']
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

FASTFUELS_DTYPE_SIZE_BYTES = 4
ff_files = ['topo.dat', 'treesfueldepth.dat', 'treesmoist.dat', 'treesrhof.dat']
ff_fancy_names = {'topo.dat' : 'Topography [m ASL]', 'treesfueldepth.dat' : "Surface Fuel Depth [m]", 
                  'treesmoist.dat' : "Fuel Moisture [g H2O / g Fuel]", 'treesrhof.dat' : r"Fuel Bulk Density [$kg\ m^{-3}$]"}

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
    
    final_namelist['simulation']['outputs'] = _handle_output_vars(final_namelist['simulation']['saveOutputVariables'])
    return final_namelist

def load_cli_namelist():
    options = sys.argv[1:]
    if(len(options) != 1):
        print("ERROR: Please specify the simulation yaml namelist after the command") 
        exit()

    with open(options[0], 'r') as raw_namelist:
        namelist = yaml.load(raw_namelist, Loader=yaml.FullLoader)

    namelist['simulation']['saveLocation'] = Path(namelist['simulation']['saveLocation'])
    
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
    with open(namelist['simulation']['saveLocation'] / 'metadata.json') as raw_meta:
        ff_meta = json.load(raw_meta)
    return ff_meta['nx'], ff_meta['ny'], ff_meta['nz']