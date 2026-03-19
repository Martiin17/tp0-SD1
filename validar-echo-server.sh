#!/bin/bash

MSG="hellow"
SERVER_NAME="server"
PORT=12345
NETWORK="tp0_testing_net"
SUCCESS=false

for i in {1..3}; do
    ACTUAL_RESPONSE=$(echo "$MSG" | docker run --rm -i --network "$NETWORK" busybox nc -w 2 "$SERVER_NAME" "$PORT" 2>/dev/null)

    if [ "$ACTUAL_RESPONSE" == "$MSG" ]; then
        SUCCESS=true
        break
    fi
    
    if [ "$i" -lt 3 ]; then
        sleep 1
    fi
done

if [ "$SUCCESS" = true ]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    exit 1
fi