import qf_cli
import matplotlib.pyplot as plt
import os, sys
import numpy as np
from pathlib import Path

def _main():
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
        grid = qf_cli.find_ignitions(namelist, inp_loc/file)
    stem = str.split(file, '.')[0]
    if('topo' in stem):
        cmap = 'gist_earth'
    elif('ignite' in stem): 
        cmap = "Reds" 
    else:
        cmap = "Greens"

    qf_cli.plot_field(namelist, grid[:, :, 0], saveas=save_figures / f'{stem}.png', cmap=cmap)

if __name__ == "__main__":
    _main()
