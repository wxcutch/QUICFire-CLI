import qf_cli
from pathlib import Path
import quicfire_tools as qft
import os
import xarray as xr

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
        dask_array = outputs.to_dask(var)
        xr.DataArray(dask_array, dims=['t', 'z', 'y', 'x'])\
            .to_netcdf(nc_loc / f'{var}.nc')
    print(f"Finished writing outputs to netcdf at {nc_loc}")
            

if __name__ == "__main__":
    _main()
