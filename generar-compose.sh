#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "Use: $0 <exit_file> <number_of_clients>"
    exit 1
fi

echo "Name exit file: $1"
echo "Number of clients: $2"

python3 script_ej1.py "$1" "$2"