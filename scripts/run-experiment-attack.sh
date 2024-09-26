#!/bin/bash

set -e
set -u

# Define packet size and paths
MM_PKT_SIZE=1504  # bytes
SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")
export SCRIPT_PATH
EXPERIMENTS_PATH=$(realpath $SCRIPT_PATH/../)
# GENERICCC_PATH=$(realpath $EXPERIMENTS_PATH/../ccas/genericCC)
RAMDISK_PATH=/mnt/ramdisk
RAMDISK_DATA_PATH=$RAMDISK_PATH/$DATA_DIR
mkdir -p $RAMDISK_DATA_PATH

# Parameters
pkts_per_ms=$1
delay_ms=$2
buf_size_bdp=$3
cca=$4
delay_uplink_trace_file=$5
cbr_uplink_trace_file=$6
downlink_trace_file=$7
port=$8
n_parallel=$9
attack_rate=${11}       # Dynamic attack rate input
queue_size=${12}        # Queue size for attack
delay_budget=${13}      # Max allowable delay for attack
#tbf_size_bdp=${10}

is_genericcc=false
if [[ $cca == genericcc_* ]]; then
    is_genericcc=true
fi

log_dmesg=true
if [[ n_parallel -gt 1 ]] || [[ is_genericcc == true ]]; then
    log_dmesg=false
fi

# Derivations for buffer size
bdp_bytes=$(echo "$MM_PKT_SIZE*$pkts_per_ms*2*$delay_ms" | bc)
buf_size_bytes=$(echo "$buf_size_bdp*$bdp_bytes/1" | bc)
exp_tag="rate[$pkts_per_ms]-delay[$delay_ms]-buf_size[$buf_size_bdp]-cca[$cca]"

# Paths for logs and telemetry
iperf_log_path=$DATA_PATH/$exp_tag.json
if [[ -f $iperf_log_path ]]; then
    rm $iperf_log_path
fi

uplink_log_path=$RAMDISK_DATA_PATH/$exp_tag.log
if [[ -f $uplink_log_path ]]; then
    rm $uplink_log_path
fi

uplink_log_path_delay_box=$RAMDISK_DATA_PATH/$exp_tag.jitter_log
if [[ -f $uplink_log_path_delay_box ]]; then
    rm $uplink_log_path_delay_box
fi

dmesg_log_path=$RAMDISK_DATA_PATH/$exp_tag.dmesg
if [[ -f $dmesg_log_path ]]; then
    rm $dmesg_log_path
fi

#for attack logging
attack_log_path=$RAMDISK_DATA_PATH/$exp_tag-attack.log
if [[ -f $attack_log_path ]]; then
    rm $attack_log_path
fi

# Start the server (iperf3 or genericCC)
if [[ $is_genericcc == true ]]; then
    echo "Using genericCC"
    $GENERICCC_PATH/receiver $port &
    server_pid=$!
else
    echo "Using iperf"
    iperf3 -s -p $port &
    server_pid=$!
fi
echo "Started server: $server_pid"

if [[ $log_dmesg == true ]]; then
    # Start dmesg logging for kernel messages
    sudo dmesg --clear
    dmesg --level info --follow --notime 1> $dmesg_log_path 2>&1 &
    dmesg_pid=$!
    echo "Started dmesg logging with: $dmesg_pid"
fi

# Start client with the attack module (dynamic attack logic)
echo "Starting client with dynamic attack logic"
export RAMDISK_DATA_PATH
export port
export cca
export iperf_log_path

export uplink_log_path
export cbr_uplink_trace_file
export downlink_trace_file
export buf_size_bytes
export genericcc_logfilepath
export tbf_size_bytes
export pkts_per_ms
export delay_ms
export attack_rate
export queue_size
export delay_budget

# Run the attack module with dynamic delay calculation and queue handling
mm-bbr-attack $attack_rate $queue_size $delay_budget --uplink-log="$uplink_log_path_delay_box" --attack-log="$attack_log_path" \
    $SCRIPT_PATH/bottleneck_box.sh

# Move uplink log
if [[ $log_uplink == true ]]; then
    mv $uplink_log_path_delay_box $DATA_PATH
fi

# Move attack log
if [[ -f $attack_log_path ]]; then
    mv $attack_log_path $DATA_PATH
fi

# Sleep to allow for cleanup
echo "Sleeping for cleanup"
sleep 5

# Kill the server
echo "Killing server"
kill $server_pid

if [[ $log_dmesg == true ]]; then
    echo "Killing dmesg logging"
    kill $dmesg_pid
    mv $dmesg_log_path $DATA_PATH
fi

# Move genericCC logs if they exist
if [[ $is_genericcc == true ]] && [[ -f $genericcc_logfilepath ]]; then
    mv $genericcc_logfilepath $DATA_PATH
fi

set +e
set +u
