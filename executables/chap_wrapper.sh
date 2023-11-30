#!/bin/bash

set -e
#set -x
if [ -z "$1" ]; then
    echo "chap wrapper needs the pipeline yaml file to be passed as the first argument"
    exit 1
fi
source /opt/conda/etc/profile.d/conda.sh
#conda activate chap 
conda activate edd

echo "Untarring input data\n"
tar xvf data.tar

CHAP $1
