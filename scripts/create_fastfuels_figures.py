from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import qf_cli
import os


def _main():
    namelist = qf_cli.load_cli_namelist()
    ff_loc = namelist['simulation']['saveLocation']
    save_figures = Path(ff_loc / 'fastfuels_figures')
    if not os.path.isdir(save_figures):
        os.mkdir(save_figures)

    if(not qf_cli.all_ff_present(ff_loc)):
        print("WARNING: Missing one or more FastFuels files")
    
    for file in qf_cli.ff_files:
        try: 
            grid = qf_cli.get_grid_from_raw_dat(namelist, ff_loc / file)
        except FileNotFoundError:
            print(f"ERROR: missing {file}")

        grid_shape = grid.shape
        label = f'z = 0 {qf_cli.ff_fancy_names[file]}' if grid_shape[-1] > 1 else qf_cli.ff_fancy_names[file]
        stem = str.split(file, '.')[0]
        cmap = "gist_earth" if ("topo" in stem) else "Greens"
        qf_cli.plot_field(namelist, grid[:, :, 0], cbar_label=label, saveas=save_figures / f'{stem}.png', cmap=cmap)

if __name__=="__main__":
    _main()