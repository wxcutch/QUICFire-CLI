import json
from pathlib import Path
import numpy as np
import struct
import matplotlib.pyplot as plt
from qf_cli import *


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

def _plot_field(namelist, field, vmin=None, vmax=None, cmap="Greens", cbar_label=None, saveas="", size_base=6):
    nx, ny, _ = get_nx_ny_nz(namelist)

    x_axis = np.arange(nx) * namelist['domain']['horizontalGridSize']
    y_axis = np.arange(ny) * namelist['domain']['horizontalGridSize']
    fig, ax = plt.subplots(1, 1, subplot_kw={'aspect':'equal'}, figsize=(size_base, size_base * (float(ny / nx) - 0.1)))

    try:
        grid_mesh = ax.pcolormesh(x_axis, y_axis, field.T, cmap=plt.get_cmap(cmap), vmin=vmin, vmax=vmax)    
    except TypeError:
        grid_mesh = ax.pcolormesh(x_axis, y_axis, field, cmap = plt.get_cmap(cmap), vmin=vmin, vmax=vmax)
 
    plt.colorbar(grid_mesh, label=cbar_label)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")

    plt.tight_layout()
    plt.savefig(saveas)

if __name__=="__main__":
    _main()