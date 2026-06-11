#!/bin/zsh
echo "-------------------------------------------------------"
echo " QUIC-Fire Based POD Boundary Assessor v0.0 - May 2026"
echo "-------------------------------------------------------"

export TEST_ENVIRONMENT_NAME=$1
export CONDA=$(which conda)

if [[ -n $TEST_ENVIRONMENT_NAME ]]; then
    echo "Looking for conda environment \"$TEST_ENVIRONMENT_NAME\""
    if [[ -z CONDA ]]; then
        echo "ERROR: Could not locate conda. Remove additional arguments to check default path."
        exit
    fi

    export CONDA_ROOT="${CONDA%/*}"
    export CONDA_ENVS="${CONDA_ROOT%/*}"

    export PYTHON="$CONDA_ENVS/envs/$TEST_ENVIRONMENT_NAME/bin/python"
    if [[ ! -e $PYTHON ]]; then
        echo "ERROR: couldn't find environment $TEST_ENVIRONMENT_NAME \n"
        exit
    else
        echo "Found the environment\n"
    fi
else
    echo 'Checking current environment          (hint: put conda environment name after script to test a specific conda environment)\n'
    export PYTHON=$(which python)
fi

if [[ ! -e $PYTHON ]]; then 
    echo "ERROR: located python was not an executable ($PYTHON)\n"
    exit
else
    echo "Python found! ($PYTHON)\n"
fi

echo " Testing for required modules"
echo "------------------------------"

while read -r line; do
    # throw in a dummy API key so the test doesn't crash if the user hasn't set it yet
    # shouldn't overwrite the key if the user already set it
    if [[ $line == "fastfuels_sdk" ]]; then
        export FASTFUELS_API_KEY="1"
    fi
    $PYTHON -c "import $line" && echo "Found $line"
    echo "\n"
done < requirements.txt
