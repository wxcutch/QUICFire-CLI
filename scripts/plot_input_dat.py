import qf_cli
import matplotlib.pyplot as plt
import os, sys
import numpy as np
from pathlib import Path

def find_ignitions(namelist, input_file):
    nx, ny, nz = qf_cli.get_nx_ny_nz(namelist)
    ignite_mask = np.zeros((nx, ny, 1))
    with open(input_file, 'r') as buffer:
        ignition_file_lines = buffer.readlines()
    ignitions = ignition_file_lines[6:] #throwing out the header
    if(len(ignitions) < 1):
        return ignite_mask
    
    for line in ignitions:
        ignite_x, ignite_y, t = str.split(line)
        ignite_mask[int(ignite_x) - 1, int(ignite_y) - 1, :] = 1
    return ignite_mask

namelist = qf_cli.load_cli_namelist(allow_multiple_files=True)
if(len(sys.argv[1:]) != 2 or "-h" in sys.argv[1:]):
    print('Please put name of the input file you wish to plot after the namelist')

file = sys.argv[2]
print(f"Will plot {file}")

inp_loc = namelist['simulation']['saveLocation']
save_figures = Path(inp_loc / 'input_figures')
if(not os.path.isdir(save_figures)):
    os.mkdir(save_figures)

if('ignite' not in file): 
    grid = qf_cli.get_grid_from_raw_dat(namelist, inp_loc / file)
else:
    grid = find_ignitions(namelist, inp_loc/file)
stem = str.split(file, '.')[0]
if('topo' in stem):
    cmap = 'gist_earth'
elif('ignite' in stem): 
    cmap = "Reds" 
else:
    cmap = "Greens"

qf_cli.plot_field(namelist, grid[:, :, 0], saveas=save_figures / f'{stem}.png', cmap=cmap)
