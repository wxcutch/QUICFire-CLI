import qf_cli
import numpy as np
import matplotlib.pyplot as plt
from plot_input_dat import find_ignitions

def _main():
    namelist = qf_cli.load_cli_namelist()

    input_locations = namelist['simulation']['saveLocation']

    #base of topo
    topo = qf_cli.get_grid_from_raw_dat(namelist, input_locations / 'topo.dat')
    #shade areas with 0 fuels in gray
    fuel_density = qf_cli.get_grid_from_raw_dat(namelist, input_locations / 'treesrhof.dat')
    #add ignitions on top
    ignition = find_ignitions(namelist, input_locations/'ignite.dat')

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={'aspect':'equal'})
    nx, ny, nz = qf_cli.get_nx_ny_nz(namelist)
    x_axis = np.arange(nx) * namelist['domain']['horizontalGridSize']
    y_axis = np.arange(ny) * namelist['domain']['horizontalGridSize']

    fuel_density_mask = (fuel_density[:, :, 0].T <= 0.01).astype(float)
    ignition_mask = ignition[:, :, 0].T

    ignition_mask[ignition_mask == 0] = np.nan
    fuel_density_mask[fuel_density_mask < 0.5] = np.nan

    topo_mesh = ax.pcolormesh(x_axis, y_axis, topo[:, :, 0].T, cmap=plt.get_cmap('gist_earth'))
    no_fuels_mesh = ax.pcolormesh(x_axis, y_axis, fuel_density_mask, cmap=plt.get_cmap('Greys_r'), alpha=0.3)
    ignition_mesh = ax.pcolormesh(x_axis, y_axis, ignition_mask, cmap=plt.get_cmap('Reds'), vmin=0, vmax=1.5)

    ax.set_xlabel('x [m]')
    ax.set_ylabel('y [m]')
    plt.colorbar(topo_mesh, label='Elevation ASL [m]')
    plt.savefig(input_locations / 'setup_map.png')

if __name__ == "__main__":
    _main()
