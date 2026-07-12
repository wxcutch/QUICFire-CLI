import qf_cli
import qf_simulation_setup

def _main():
    namelist = qf_cli.load_cli_namelist()
    qf_simulation_setup.write_ignition(namelist)

if __name__ == "__main__":
    _main()
