import qf_cli
from pathlib import Path
import quicfire_tools as qft
import os
import netCDF4 as nc

def _main():
    namelist = qf_cli.load_cli_namelist()
    output_loc = Path(namelist['simulation']['saveLocation'] / 'Output')
    
    nc_loc = Path(output_loc / 'netcdf')
    if(not os.path.isdir(nc_loc)):
        os.mkdir(nc_loc)

    inputs = qft.SimulationInputs.from_directory(namelist['simulation']['saveLocation'])
    outputs = qft.SimulationOutputs.from_simulation_inputs(output_loc, inputs)
    
    output_vars = outputs.list_outputs()
    
    for var in output_vars:
        full_grid = outputs.get_output(var).to_netcdf(nc_loc)
    print(f"Finished writing outputs to netcdf at {nc_loc}")
            

if __name__ == "__main__":
    _main()
