import json
from qf_simulation_setup import *
from pathlib import Path
import numpy as np
import struct
import matplotlib.pyplot as plt

DTYPE_SIZE_BYTES = 4
ff_files = ['topo.dat', 'treesfueldepth.dat', 'treesmoist.dat', 'treesrhof.dat']
ff_fancy_names = {'topo.dat' : 'Topography [m ASL]', 'treesfueldepth.dat' : "Surface Fuel Depth [m]", 
                  'treesmoist.dat' : "Fuel Moisture [g H2O / g Fuel]", 'treesrhof.dat' : r"Fuel Bulk Density [$kg\ m^{-3}$]"}

def _main():
    namelist = load_cli_namelist()
    ff_loc = namelist['simulation']['saveLocation']
    save_figures = Path(ff_loc / 'fastfuels_figures')
    if not os.path.isdir(save_figures):
        os.mkdir(save_figures)

    if(not all_ff_present(ff_loc)):
        print("WARNING: Missing one or more FastFuels files")
    
    for file in ff_files:
        try: 
            grid = get_grid_from_raw_dat(namelist, ff_loc / file)
        except FileNotFoundError:
            print(f"ERROR: missing {file}")

        grid_shape = grid.shape
        label = f'z = 0 {ff_fancy_names[file]}' if grid_shape[-1] > 1 else ff_fancy_names[file]
        stem = str.split(file, '.')[0]
        cmap = "gist_earth" if ("topo" in stem) else "Greens"
        _plot_field(namelist, grid[:, :, 0], cbar_label=label, saveas=save_figures / f'{stem}.png', cmap=cmap)
        

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
    is_2d = int(fsize / (nx * ny)) == DTYPE_SIZE_BYTES
    grid_nz = 1 if is_2d == True else nz
    
    with open(floc, 'rb') as fstream:
        pre1 = struct.unpack('i', fstream.read(4))[0]
        grid = np.frombuffer(fstream.read(nx * ny * grid_nz * DTYPE_SIZE_BYTES), 'f').reshape((nx, ny, grid_nz), order='F')
    return grid

def _plot_field(namelist, field, vmin=None, vmax=None, cmap="Greens", cbar_label=None, saveas="", size_base=4):
    nx, ny, _ = get_nx_ny_nz(namelist)
    grid_ratio = float(nx / ny)

    x_axis = np.arange(nx) * namelist['domain']['horizontalGridSize']
    y_axis = np.arange(ny) * namelist['domain']['horizontalGridSize']
    fig, ax = plt.subplots(1, 1, subplot_kw={'aspect':'equal'}, figsize=(size_base, size_base * (float(ny / nx) - 0.6)))

    try:
        grid_mesh = ax.pcolormesh(x_axis, y_axis, field.T, cmap=plt.get_cmap(cmap), vmin=vmin, vmax=vmax)    
    except TypeError:
        grid_mesh = ax.pcolormesh(x_axis, y_axis, field, cmap = plt.get_cmap(cmap), vmin=vmin, vmax=vmax)
 
    plt.colorbar(grid_mesh, label=cbar_label)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")

    # plt.tight_layout()
    plt.savefig(saveas)

if __name__=="__main__":
    _main()