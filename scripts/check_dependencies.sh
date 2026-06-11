echo "------------------------------------------"
echo "QUIC-Fire CLI Dependency Checker"
echo "------------------------------------------"
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
        echo "ERROR: couldn't find environment $TEST_ENVIRONMENT_NAME"
        exit
    else
        echo "Found the environment"
    fi
else
    echo 'Checking current environment'
    echo '(hint: put conda environment name after script to test a specific conda environment)'
    export PYTHON=$(which python)
fi

if [[ ! -e $PYTHON ]]; then 
    echo "ERROR: located python was not an executable ($PYTHON)"
    exit
else
    echo "Python found! ($PYTHON)"
fi

echo "------------------------------------------"
echo " Testing for required modules"
echo "------------------------------------------"

while read -r line; do
    $PYTHON -c "import $line" && echo "Found $line"
done < resources/requirements.txt
