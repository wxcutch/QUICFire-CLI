import qf_cli
import matplotlib.pyplot as plt
import os
import sys
from pathlib import Path
import copy
import numpy as np
import quicfire_tools as qft

def _main():
    ens_namelist = qf_cli.load_cli_namelist(allow_multiple_files=True)
    candidates = os.listdir(ens_namelist['simulation']['saveLocation'])
    members = [Path(ens_namelist['simulation']['saveLocation'] / folder) for folder in candidates 
               if (os.path.isdir(ens_namelist['simulation']['saveLocation'] / folder) and 'QUIC_fire.inp' in os.listdir(ens_namelist['simulation']['saveLocation'] / folder))]
    if(len(sys.argv[1:]) > 1):
        tokens = sys.argv[2:]
        print(f"will look for tokens {tokens}")
        candidate_members = copy.deepcopy(members)
        members = []
        for token in tokens:
            for member in candidate_members:
                if(token in str(member)):
                    members.append(member)
                    candidate_members.remove(member)
    if(len(members) == 0):
        print("ERROR: couldn't find members to run the script with")
        exit()

    print(members[0] / 'namelist.yml')
    sample_namelist = qf_cli.load_cli_namelist(from_file=(members[0] / 'namelist.yml'))

    nx, ny, _ = qf_cli.get_nx_ny_nz(sample_namelist)
    dx = sample_namelist['domain']['horizontalGridSize']
    dy = dx

    prob_mask, n_mems = accumulate_nburnt(members, nx, ny)
    
    fig, ax = plt.subplots(figsize=(8.5, 8.5), subplot_kw={'aspect':'equal'})
    x = np.arange(nx) * dx
    y = np.arange(ny) * dy
    prob_mesh = ax.pcolormesh(x, y, prob_mask, cmap='jet')
    ax.set_xlabel('x [m]')
    ax.set_ylabel('y [m]')
    plt.colorbar(prob_mesh, label="N members where pixel burned")
    tokens_string = ""
    for token in tokens:
        tokens_string += f"_{token}"
    plt.savefig(ens_namelist['simulation']['saveLocation'] / f'ensemble_members_burned{tokens_string}.png')
    
def accumulate_nburnt(members, nx, ny):
    nburnt = np.zeros((ny, nx))
    for member in members:
        print(f"aggregating {member}")
        inputs = qft.SimulationInputs.from_directory(member)
        outputs = qft.SimulationOutputs.from_simulation_inputs(member / 'Output', inputs)
        
        output_vars = outputs.list_outputs()
        test_product = 'mburnt_integ' if 'mburnt_integ' in output_vars else 'surfEnergy'
        if(test_product not in output_vars):
            print("ERROR: Missing required variable. Please rerun your simulations to give either mass burnt or surface energy to run this script")
        prod = outputs.get_output(test_product).to_numpy()
        total = np.sum(prod, axis=(0, 1))
        mask = total > 0
        nburnt += mask
    return nburnt, len(members)
        

if __name__=="__main__":
    _main()
