import quicfire_tools as qft
import os
import numpy as np
from pathlib import Path
from getopt import getopt
import netCDF4 as nc
import qf_cli
import sys
import time

def retrieve_energy_grid(qft_outputs):
    var_grid = qft_outputs.get_output('surfEnergy').to_numpy()
    var_grid = np.squeeze(var_grid)
    return var_grid

def calc_toa(energy_grid, dt=1):
    burning_mask = np.full(energy_grid.shape, np.nan)
    burning_mask[energy_grid > 0] = 1
    # for t in range(nt):
    #     burning_mask[t, :, :] *= dt*t
    t = np.arange(nt) * dt
    burning_mask = (burning_mask.T * t).T

    toa = np.nanmin(burning_mask, axis=0)
    return toa

def determine_output_type(max_value, min_value=0, integer=False, min_sig_fig=6):
    abs_max = max(abs(max_value), abs(min_value))

    if(integer == False):
        default_type = np.float32
        if(min_sig_fig > np.log10(np.finfo(default_type).resolution) or abs_max > np.finfo(default_type).max):
            return np.float64
        else:
            return default_type
    else:
        can_be_unsigned = (min_value >= 0)
        bits_to_represent_max = np.ceil(np.log2(abs_max))
        if(can_be_unsigned): 
            bits_to_represent_max -= 1
        
        if(bits_to_represent_max <= 7):
            if(can_be_unsigned == True): return np.uint8 
            else: return np.int8
        elif(bits_to_represent_max <= 15):
            if(can_be_unsigned == True): return np.uint16
            else: return np.int16
        elif(bits_to_represent_max <= 32): 
            if(can_be_unsigned == True): return np.uint32
            else: return np.int32
        elif(bits_to_represent_max <= 64):
            if(can_be_unsigned == True): return np.uint64
            else: return np.int64
        else:
            print("ERROR: Data too large to store with conventional integer datatypes")
            exit()
        
if __name__ == "__main__":
    start_time = time.time()
    # inp_loc, out_loc, save_loc = get_options()
    namelist = qf_cli.load_cli_namelist()
    inp_loc = namelist['simulation']['saveLocation']
    out_loc = namelist['simulation']['saveLocation'] / 'Output'
    product_folder = Path(namelist['simulation']['saveLocation'] / 'derived_products')
    if(not os.path.isdir(product_folder)):
        os.mkdir(product_folder)

    save_loc = product_folder / 'surfEnergy_products.nc'
    print(f'inputs: \"{inp_loc}\" outputs: \"{out_loc}\" save as: \"{save_loc}\"' )
    inputs = qft.SimulationInputs.from_directory(inp_loc)
    outputs = qft.SimulationOutputs.from_simulation_inputs(out_loc, inputs)
    
    energy = retrieve_energy_grid(outputs)

    nt, ny, nx = energy.shape
    dz = inputs.quic_fire.dz
    dy = inputs.qu_simparams.dy
    dx = inputs.qu_simparams.dx
    dt = inputs.quic_fire.fire_time_step

    toa = calc_toa(energy, dt=dt)
    total_energy = np.sum(energy, axis=0)
    max_inst_energy = np.max(energy, axis=0)

    max_toa = np.nanmax(toa)
    max_energy = np.max(max_inst_energy)

    toa_type = determine_output_type(max_toa, integer=True)
    energy_type = determine_output_type(max_energy, integer=True)

    with nc.Dataset(save_loc, 'w', clobber=True) as nc_out:
        x_dim = nc_out.createDimension('x', size=nx)
        y_dim = nc_out.createDimension('y', size=ny)

        nc_out.dx = dx
        nc_out.dy = dy
        nc_out.dt = dt
        nc_out.nt = nt

        toa_out = nc_out.createVariable('TimeOfArrival', datatype=toa_type, dimensions=[y_dim, x_dim])
        energy_out = nc_out.createVariable('CumulativeEnergy', datatype=energy_type, dimensions=[y_dim, x_dim])
        inst_energy_out = nc_out.createVariable('MaxInstantaneousEnergy', datatype=energy_type, dimensions=[y_dim, x_dim])

        toa_out[:] = toa
        energy_out[:] = total_energy
        inst_energy_out[:] = max_energy
    print(f"Total execution time: {time.time() - start_time}")