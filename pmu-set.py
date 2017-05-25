#!/usr/bin/env python

import os
import sys
import struct
import argparse
from terminaltables import AsciiTable

############## INTERNAL VARIABLES ##############
num_core = 0
num_skt = 0
num_core_skt = 0

num_pmu = 8

############## MSR REGISTRIES ##############

# Enable FIXED and PMU comuters
IA32_PERF_GLOBAL_CTRL = 0x38F
CONF_ENABLE_FIXED = 0x700000000
CONF_ENABLE_PMU = 0xFF

# FIXED COUNTER configuration (instructions retired, CLK_CURR, CLK_REF)
IA32_FIXED_CTR_CTRL = 0x38D
CONF_START_FIXED = 0x333

# PMU configuration
IA32_PERFEVTSELX_ADDR = [0x186, 0x187, 0x188, 0x189, 0x18A, 0x18B, 0x18C, 0x18D]
IA32_PMCX = [0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8]
CONF_START_PMU = 0x400000

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
    
def read_pmu():
    conf = ["Fixed 0"]
    conf.append("Fixed 1")
    conf.append("Fixed 2")
    for i in range(num_pmu):
        conf.append("PMU " + str(i))
    
    table_data = []
    table_data.append(conf)
    for c in range(num_core):
        core_conf = []
        
        reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)
        
        enable_fixed_0 = (reg_perf_global_ctrl >> 32) & 1
        if enable_fixed_0 == 1:
            core_conf.append("Enable")
        else:
            core_conf.append("Disable")
            
        enable_fixed_1 = (reg_perf_global_ctrl >> 33) & 1
        if enable_fixed_1 == 1:
            core_conf.append("Enable")
        else:
            core_conf.append("Disable")
            
        enable_fixed_2 = (reg_perf_global_ctrl >> 34) & 1
        if enable_fixed_2 == 1:
            core_conf.append("Enable")
        else:
            core_conf.append("Disable")
        
        for j in range(num_pmu):
            enable_pmu = reg_perf_global_ctrl & 1
            if enable_pmu == 1:
                core_conf.append("Enable")
            else:
                core_conf.append("Disable")
        table_data.append(core_conf)
        
    table = AsciiTable(table_data)
    print table.table
    

# Main
if __name__ == "__main__":
    check_requirements()

    init_config()

    core = [False] * num_core
    fixed_counter = None
    pmu_counter = None
    pmu = None
    event = None
    umask = None

    # Parse arguments
    parser = argparse.ArgumentParser(description='Tool for PMU setting')
    parser.add_argument('-c', '--core', help='Set PMU for core $C [Default all]', required=False, type=int, choices=xrange(0, num_core-1))
    parser.add_argument('-ef', '--enable-fix', help='Enable fixed counter', required=False)
    parser.add_argument('-df', '--disable-fix', help='Disable fixed counter', required=False)
    parser.add_argument('-ep', '--enable-pmu', help='Enable PMU counter', required=False)
    parser.add_argument('-dp', '--disable-pmu', help='Disable PMU counter', required=False)
    parser.add_argument('-p', '--pmu-number', help='Set the PMU registry', required=False, type=int, choices=xrange(0, num_pmu-1))
    parser.add_argument('-u', '--pmu-umask', help='Set the PMU umask', required=False, type=str)
    parser.add_argument('-e', '--pmu-event', help='Set the PMU event', required=False, type=str)
    parser.add_argument('-r', '--reset', help='Reset PMU and fixed counters', required=False)
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        read_pmu()
        sys.exit(1)
    if args.pmu_number is None or args.pmu_event is None or args.umask is None:
        sys.stderr.write("[ERROR] Need to be specify PMU registry, PMU event and PMU umask!\n")
        sys.exit(-1)
    elif args.pmu_number >= num_pmu or args.pmu_number < 0:
        sys.stderr.write("[ERROR] PMU registries ranged from 1 to " + str(num_pmu) + "!\n")
        sys.exit(-1)
        
    if args.core is not None:
        core[args.core] = True
    else:
        core = [True] * num_core
    
    if args.enable_fix is not None:
        fixed_counter = True
    elif args.disable_fix is not None:
        fixed_counter = False

    if args.enable_pmu is not None:
        pmu_counter = True
    elif args.disable_pmu is not None:
        pmu_counter = False

    pmu = args.pmu_number
    umask = args.umask
    event = args.pmu_event

    # Apply configurations
    for c in core:
        if c is not None:
            if fixed_counter is not True:
                reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)
                reg_fixed_ctr_ctrl = read_msr(IA32_FIXED_CTR_CTRL, c)
                
                if fixed_counter is True:
        			reg_perf_global_ctrl = reg_perf_global_ctrl | CONF_ENABLE_FIXED
        			reg_fixed_ctr_ctrl = reg_fixed_ctr_ctrl | CONF_START_FIXED
                elif fixed_counter is False:
        			reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_ENABLE_FIXED
        			reg_fixed_ctr_ctrl = reg_fixed_ctr_ctrl & ~CONF_START_FIXED
           
                write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)
                write_msr(IA32_FIXED_CTR_CTRL, reg_fixed_ctr_ctrl, c)
                
            if pmu_counter is not None:
                reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)
                
                if pmu_counter is True:
                    reg_perf_global_ctrl = reg_perf_global_ctrl | CONF_ENABLE_FIXED
                elif pmu_counter is False:
                    reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_ENABLE_FIXED
                
                write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)
                
            reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[pmu], c)
            reg_ia32_perfevtselx = reg_ia32_perfevtselx | CONF_START_PMU
            reg_ia32_perfevtselx = reg_ia32_perfevtselx | (umask << 8)
            reg_ia32_perfevtselx = reg_ia32_perfevtselx | event
            write_msr(IA32_PERFEVTSELX_ADDR[pmu], reg_ia32_perfevtselx, c) 