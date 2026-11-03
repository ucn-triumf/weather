#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$MIDASSYS/python

# go to dir of this file
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

# create virtual env
if [ ! -d "./.env" ]; then
    echo "Creating python virtual environment" 
    python3 -m venv env
    
    # install dependencies
    source .env/bin/activate
    pip install -r requirements.txt
else
    # source venv
    source env/bin/activate
fi

# start script
python3 frontend.py

