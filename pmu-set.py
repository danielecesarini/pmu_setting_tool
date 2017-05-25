#!/usr/bin/env python

import os
import sys
import struct
import argparse

############## INTERNAL VARIABLES ##############
num_core = 0
num_skt = 0
num_core_skt = 0

num_pmu = 8

############## MSR REGISTRIES ##############

# FIXED COUNTER and PMU enabling
IA32_PERF_GLOBAL_CTRL = 0x38F
CONF_TO_ENABLE_FIXED = 0x700000000
CONF_TO_ENABLE_PMU = 0xFF

# FIXED COUNTER configuration (instructions retired, CLKCURR (MPERF), CLKREF (APERF))
IA32_FIXED_CTR_CTRL = 0x38D
CONF_TO_START_FIXED = 0x333

# PMU configuration
IA32_PERFEVTSELX_ADDR = [0x186, 0x187, 0x188, 0x189, 0x18A, 0x18B, 0x18C, 0x18D]

# PMU
IA32_PMCX = [0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8]

##################################################

# Read a MSR registry
def read_msr(msr, cpu):
    f = os.open('/dev/cpu/%d/msr' % (cpu,), os.O_RDONLY)
    os.lseek(f, msr, os.SEEK_SET)
    val = struct.unpack('Q', os.read(f, 8))[0]
    os.close(f)
    return val

# Write a MSR registry
def write_msr(msr, val, cpu):
    f = os.open('/dev/cpu/%d/msr' % (cpu,), os.O_WRONLY)
    os.lseek(f, msr, os.SEEK_SET)
    os.write(f, struct.pack('Q', val))
    os.close(f)

# Check requisites of the system
def check_requirements():
    # Check root permission
    uid = os.getuid()
    if uid != 0:
        sys.stderr.write("[WARNING] Need to be root to execute this software!\n")
        exit(-1)

    # Check if MSR module is loaded
    if not os.path.exists("/dev/cpu/0/msr"):
        sys.stderr.write("[WARNING] MSR module is not loaded!\n")
        exit(-2)


# Default initial configuration
def init_config():
    global num_core, num_skt, num_core_skt

    # Read the number of virtual CPUs and sockets
    with open("/proc/cpuinfo", "r") as f:
        conf_lines = f.readlines()
        for cl in conf_lines:
            if "physical id" in cl:
                num_core += 1
                skt = cl.replace(" ", "").split(":")[1]
                if (int(skt)+1) > num_skt:
                    num_skt += 1
    num_core_skt = num_core / num_skt

# Main
if __name__ == "__main__":
    check_requirements()

    init_config()

    core = [None] * num_core
    fix_counter = None
    pmu_counter = None
    pmu = None
    event = None
    umask = None

    # Parse arguments
    parser = argparse.ArgumentParser(description='Tool for PMU setting')

    parser.add_argument('-c', '--core', help='Set PMU for core $C', required=False, type=int, choices=xrange(0, num_core-1))
    parser.add_argument('-ef', '--enable-fix', help='Enable fixed counters', required=False)
    parser.add_argument('-df', '--disable-fix', help='Disable fixed counters', required=False)
    parser.add_argument('-ep', '--enable-pmu', help='Enable PMU counters', required=False)
    parser.add_argument('-dp', '--disable-pmu', help='Disable PMU counters', required=False)
    parser.add_argument('-p', '--pmu-number', help='Set PMU registry number $X', required=False, type=int, choices=xrange(0, num_pmu))
	parser.add_argument('-e', '--pmu-event', help='Set PMU with event', required=False, type=str)
	parser.add_argument('-u', '--pmu-umask', help='Set PMU with umask', required=False, type=str)
    parser.add_argument('-r', '--reset', help='Reset PMU and fixed counters', required=False)
    
    if len(sys.argv) == 1:
    	print "nothing"
    elif args.reset is not None:
    	if args.core is not None:
    		core[args.core] = False
    	else:
    		core = [False] * num_core
    else:
    	if args.core is not None:
    		core[args.core] = True
    	else:
    		core = [True] * num_core

    	if args.enable_fix is not None:
    		fix_counter = True
    	if args.disable_fix is not None:
    		fix_counter = False

    	if args.enable_pmu is not None:
    		pmu_counter = True
    	if args.disable_pmu is not None:
    		pmu_counter = False

    	if args.pmu_event is not None:
    		event = args.pmu_event
    	if args.umask is not None:
    		umask = args.umask

    # Apply configurations
    for c in core:
    	if c is not None:
    		if fix_counter is True:
    			reg_perf_global_ctrl = read(IA32_PERF_GLOBAL_CTRL, c)
    			reg_fixed_ctr_ctrl = read(IA32_FIXED_CTR_CTRL, c)

    			reg_perf_global_ctrl = reg_perf_global_ctrl | CONF_TO_ENABLE_FIXED
    			reg_fixed_ctr_ctrl = reg_fixed_ctr_ctrl | CONF_TO_START_FIXED

    			write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)
    			write_msr(IA32_FIXED_CTR_CTRL, reg_fixed_ctr_ctrl, c)
    		elif fix_counter is False:
    			reg_perf_global_ctrl = read(IA32_PERF_GLOBAL_CTRL, c)
    			reg_fixed_ctr_ctrl = read(IA32_FIXED_CTR_CTRL, c)

    			reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_TO_ENABLE_FIXED
    			reg_fixed_ctr_ctrl = reg_fixed_ctr_ctrl & ~CONF_TO_START_FIXED

    			write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)
    			write_msr(IA32_FIXED_CTR_CTRL, reg_fixed_ctr_ctrl, c)

    		if pmu_counter is True:
    			reg_perf_global_ctrl = read(IA32_PERF_GLOBAL_CTRL, c)

