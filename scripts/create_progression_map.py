import qf_cli
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path
import xarray as xr

def _main():
    namelist = qf_cli.load_cli_namelist()
    if(namelist == None):
        print("ERROR: incompatible namelist")
        exit()

    derived_product_folder = Path(namelist['simulation']['saveLocation'] / 'derived_products')
    if(not os.path.isdir(derived_product_folder) or 
       not os.path.isfile(derived_product_folder / 'surfEnergy_products.nc')):
        print("ERROR: Could not find the time of arrival derived product. Please run \"derive_surfEnergy_products.py\" then try again.")
        exit()

    figure_folder = Path(namelist['simulation']['saveLocation'] / 'figures')
    if(not os.path.isdir(figure_folder)):
        os.mkdir(figure_folder)

    ds = xr.open_dataset(derived_product_folder / 'surfEnergy_products.nc')

    toa_masked = ds.TimeOfArrival.where(ds.TimeOfArrival != 0)

    qf_cli.plot_field(namelist, toa_masked, cmap='cividis', cbar_label="Earliest Time of Arrival [s]", saveas=figure_folder / 'TimeOfArrival.png')


if __name__=="__main__":
    _main()