import qf_cli
import quicfire_tools as qft
import matplotlib.pyplot as plt
import numpy as np


def _main():

    def add_anotations(ax, x, y, ignition_mask, nb_mask, terrain, windu, windv, winds_spacing=20, barbs={'half':1.25, 'full':2.5, 'flag':25}):
        ax.pcolormesh(x, y, nb_mask, cmap=plt.get_cmap('Greys_r'), alpha=0.3)
        ax.pcolormesh(x, y, ignition_mask, cmap=plt.get_cmap('Reds'), vmin=0, vmax=1.5)

        ax.barbs(x[::winds_spacing], y[::winds_spacing], windu[::winds_spacing, ::winds_spacing], 
                 windv[::winds_spacing, ::winds_spacing], barb_increments=barbs)
        ax.contour(x, y, terrain, colors='brown', linestyles='dotted')
        ax.set_xlabel('x [m]')
        ax.set_ylabel('y [m]')
        
    namelist = qf_cli.load_cli_namelist()
    inputs, outputs = qf_cli.load_qft_inputs_outputs(namelist)

    nx, ny, nz = qf_cli.get_nx_ny_nz(namelist)

    x = np.arange(nx) * namelist['domain']['horizontalGridSize']
    y = np.arange(ny) * namelist['domain']['horizontalGridSize']

    windu = outputs.get_output('windu').to_numpy()
    windv = outputs.get_output('windv').to_numpy()

    ignition = qf_cli.find_ignitions(namelist, 'ignite.dat')
    ignition_mask = ignition[:, :, 0].T
    
    fuel_density = qf_cli.get_grid_from_raw_dat(namelist, 'treesrhof.dat')
    fuel_density_mask = (fuel_density[:, :, 0].T <= 0.01).astype(float)

    ignition_mask[ignition_mask == 0] = np.nan
    fuel_density_mask[fuel_density_mask < 0.5] = np.nan

    topo = qf_cli.get_grid_from_raw_dat(namelist, 'topo.dat')
    fuel_moisture = qf_cli.get_grid_from_raw_dat(namelist, 'treesmoist.dat')
    fuel_depth = qf_cli.get_grid_from_raw_dat(namelist, 'treesfueldepth.dat')

    fig, ax = plt.subplots(2, 2, subplot_kw={'aspect':'equal'})

    topo_mesh = ax[0][0].pcolormesh(x, y, topo[:, :, 0].T, cmap=plt.get_cmap('gist_earth'))
    ax[0][0].set_title("Terrain Height ASL [m]")
    add_anotations(ax[0][0], x, y, ignition_mask, fuel_density_mask, topo, windu[:, :, 1].T, windv[:, :, 1].T)
    plt.colorbar(topo_mesh)

    density_mesh = ax[0][1].pcolormesh(x, y, fuel_density[:, :, 0].T, cmap=plt.get_cmap('Greens'))
    ax[0][1].set_title(f"Fuel Density [kg / voxel (voxel = {namelist['domain']['horizontalGridSpacing']}m x {namelist['domain']['horizontalGridSpacing']}m x {namelist['domain']['verticalGridSpacing']}m)]")
    add_anotations(ax[0][1], x, y, ignition_mask, fuel_density_mask, topo, windu[:, :, 1].T, windv[:, :, 1].T)
    plt.colorbar(density_mesh)

    moisture_mesh = ax[1][0].pcolormesh(x, y, fuel_moisture[:, :, 0].T, cmap=plt.get_cmap('BrBG'))
    ax[1][0].set_title('Fuel Moisture [g H2O / g Dry Fuel]')
    add_anotations(ax[1][0], x, y, ignition_mask, fuel_density_mask, topo, windu[:, :, 1].T, windv[:, :, 1].T)
    plt.colorbar(moisture_mesh)

    depth_mesh = ax[1][1].pcolormesh(x, y, fuel_depth[:, :, 0].T, cmap=plt.get_cmap('Oranges'))
    ax[1][1].set_title('Fuel Depth [flamelength limiting factor]')
    add_anotations(ax[1][1], x, y, ignition_mask, fuel_density_mask, topo, windu[:, :, 1].T, windv[:, :, 1].T)
    plt.colorbar(depth_mesh)

    plt.savefig(namelist['simulation']['saveLocation'] / 'initial_conditions.png')

if __name__ == "__main__":
    _main()