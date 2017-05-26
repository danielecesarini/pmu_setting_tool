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

num_pmu = None

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
IA32_FIXED_CTRX = [0x309, 0x30a, 0x30b]
IA32_PMCX = [0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8]

CONF_EN_OS_USR = 0x430000

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

def hyperthreading_enabled():
    fd = open('/proc/cpuinfo')
    cpuinfo = dict(map(str.strip, line.split(':')) for line in fd if ':' in line)
    fd.close()
    return cpuinfo['siblings'] != cpuinfo['cpu cores']

# Default initial configuration
def init_config():
    global num_core, num_skt, num_core_skt, num_pmu

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

    ht = hyperthreading_enabled()
    if ht is True:
        num_pmu = 4
    else:
        num_pmu = 8
    
def read_enable_fixed_pmu():
    table_data = []

    labels = ["IA32_PERF_GLOBAL_CTRL"]
    labels.append("Fixed 0")
    labels.append("Fixed 1")
    labels.append("Fixed 2")
    for i in range(num_pmu):
        labels.append("PMU " + str(i))
    table_data.append(labels)

    for c in range(num_core):
        reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)

        conf = ["Core " + str(c)]
        
        enable_fixed_0 = (reg_perf_global_ctrl >> 32) & 1
        if enable_fixed_0 == 1:
            conf.append("ON")
        else:
            conf.append("OFF")
            
        enable_fixed_1 = (reg_perf_global_ctrl >> 33) & 1
        if enable_fixed_1 == 1:
            conf.append("ON")
        else:
            conf.append("OFF")
            
        enable_fixed_2 = (reg_perf_global_ctrl >> 34) & 1
        if enable_fixed_2 == 1:
            conf.append("ON")
        else:
            conf.append("OFF")
        
        for j in range(num_pmu):
            enable_pmu = reg_perf_global_ctrl & 1
            if enable_pmu == 1:
                conf.append("ON")
            else:
                conf.append("OFF")
        table_data.append(conf)
        
    table = AsciiTable(table_data)
    print table.table

def read_conf_fixed():
    table_data = []

    labels = ["IA32_FIXED_CTR_CTRL"]
    labels.append("PMI 0")
    labels.append("ANY 0")
    labels.append("EN 0")
    labels.append("PMI 1")
    labels.append("ANY 1")
    labels.append("EN 1")
    labels.append("PMI 2")
    labels.append("ANY 2")
    labels.append("EN 2")

    table_data.append(labels)

    for c in range(num_core):
        reg_fixed_ctr_ctrl = read_msr(IA32_FIXED_CTR_CTRL, c)

        conf = ["Core " + str(c)]

        PMI_0 = "ON" if ((reg_fixed_ctr_ctrl >> 3) & 0x1) == 1 else "OFF"
        conf.append(PMI_0)
        ANY_0 = "ON" if ((reg_fixed_ctr_ctrl >> 2) & 0x1) == 1 else "OFF"
        conf.append(ANY_0)
        EN_0 = reg_fixed_ctr_ctrl & 0x3
        if EN_0 == 0:
            conf.append("OFF")
        elif EN_0 == 1:
            conf.append("OS")
        elif EN_0 == 2:
            conf.append("User")
        elif EN_0 == 3:
            conf.append("ALL RINGS")

        PMI_1 = "ON" if ((reg_fixed_ctr_ctrl >> 7) & 0x1) == 1 else "OFF"
        conf.append(PMI_1)
        ANY_1 = "ON" if ((reg_fixed_ctr_ctrl >> 6) & 0x1) == 1 else "OFF"
        conf.append(ANY_1)
        EN_1 = (reg_fixed_ctr_ctrl >> 4) & 0x3
        if EN_1 == 0:
            conf.append("OFF")
        elif EN_1 == 1:
            conf.append("OS")
        elif EN_1 == 2:
            conf.append("User")
        elif EN_1 == 3:
            conf.append("ALL RINGS")

        PMI_2 = "ON" if ((reg_fixed_ctr_ctrl >> 11) & 0x1) == 1 else "OFF"
        conf.append(PMI_2)
        ANY_2 = "ON" if ((reg_fixed_ctr_ctrl >> 10) & 0x1) == 1 else "OFF"
        conf.append(ANY_2)
        EN_2 = (reg_fixed_ctr_ctrl >> 8) & 0x3
        if EN_2 == 0:
            conf.append("OFF")
        elif EN_2 == 1:
            conf.append("OS")
        elif EN_2 == 2:
            conf.append("User")
        elif EN_2 == 3:
            conf.append("ALL RINGS")
              
        table_data.append(conf)

    table = AsciiTable(table_data)
    print table.table

def read_conf_pmu():
    for c in range(num_core):
        table_data = []

        labels = ["Core " + str(c)]
        labels.append("CMASK")
        labels.append("INV")
        labels.append("EN")
        labels.append("ANY")
        labels.append("INT")
        labels.append("PC")
        labels.append("E")
        labels.append("OS")
        labels.append("USR")
        labels.append("UMASK")
        labels.append("EVENT")
        table_data.append(labels)

        for j in range(num_pmu):
            reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[j], c)

            conf = ["PMU " + str(j)]

            CMASK = (reg_ia32_perfevtselx >> 24) & 0xFF
            conf.append(CMASK)

            INV = "ON" if ((reg_ia32_perfevtselx >> 23) & 1) == 1 else "OFF"
            conf.append(INV)

            EN = "ON" if ((reg_ia32_perfevtselx >> 22) & 1) == 1 else "OFF"
            conf.append(EN)

            ANY = "ON" if ((reg_ia32_perfevtselx >> 21) & 1) == 1 else "OFF"
            conf.append(ANY)

            INT = "ON" if ((reg_ia32_perfevtselx >> 20) & 1) == 1 else "OFF"
            conf.append(INT)

            PC = "ON" if ((reg_ia32_perfevtselx >> 19) & 1) == 1 else "OFF"
            conf.append(PC)

            E = "ON" if ((reg_ia32_perfevtselx >> 18) & 1) == 1 else "OFF"
            conf.append(E)

            OS = "ON" if ((reg_ia32_perfevtselx >> 17) & 1) == 1 else "OFF"
            conf.append(OS)

            USR = "ON" if ((reg_ia32_perfevtselx >> 16) & 1) == 1 else "OFF"
            conf.append(USR)

            UMASK = (reg_ia32_perfevtselx >> 8) & 8
            conf.append(UMASK)

            EVENT = reg_ia32_perfevtselx & 8
            conf.append(EVENT)

            table_data.append(conf)
        
        table = AsciiTable(table_data)
        print table.table

def read_perf_fixed():
    table_data = []

    labels = ["PERF"]
    labels.append("Fixed 0")
    labels.append("Fixed 1")
    labels.append("Fixed 2")
    table_data.append(labels)

    for c in range(num_core):
        perf = ["Core " + str(c)]
        perf.append(read_msr(IA32_FIXED_CTRX[0], c))
        perf.append(read_msr(IA32_FIXED_CTRX[1], c))
        perf.append(read_msr(IA32_FIXED_CTRX[2], c))
        table_data.append(perf)

    table = AsciiTable(table_data)
    print table.table

def read_perf_pmu():
    table_data = []

    labels = ["PERF"]
    for i in range(num_pmu):
        labels.append("PMU " + str(i))
    table_data.append(labels)

    for c in range(num_core):
        perf = ["Core " + str(c)]
        for j in range(num_pmu):
            perf.append(read_msr(IA32_PMCX[j], c))
        table_data.append(perf)

    table = AsciiTable(table_data)
    print table.table


def reset():
    for c in range(num_core):
        reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)
        reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_ENABLE_FIXED
        reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_ENABLE_PMU
        write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)

    for c in range(num_core):
        reg_fixed_ctr_ctrl = read_msr(IA32_FIXED_CTR_CTRL, c)
        reg_fixed_ctr_ctrl = reg_fixed_ctr_ctrl & ~CONF_START_FIXED
        write_msr(IA32_FIXED_CTR_CTRL, reg_fixed_ctr_ctrl, c)

    for c in range(num_core):
        for j in range(num_pmu):
            reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[j], c)
            reg_ia32_perfevtselx = reg_ia32_perfevtselx & ~0xFFFFFFFF
            write_msr(IA32_PERFEVTSELX_ADDR[j], reg_ia32_perfevtselx, c)

def is_hex(s):
    try:
        int(s, 16)
        return True
    except ValueError:
        return False

def is_int(s):
    try:
        int(s, 10)
        return True
    except ValueError:
        return False

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
    parser.add_argument('-ef', '--enable-fix', help='Enable fixed counter', required=False, action='store_true')
    parser.add_argument('-df', '--disable-fix', help='Disable fixed counter', required=False, action='store_true')
    parser.add_argument('-ep', '--enable-pmu', help='Enable PMU counter', required=False, action='store_true')
    parser.add_argument('-dp', '--disable-pmu', help='Disable PMU counter', required=False, action='store_true')
    parser.add_argument('-pmu', '--pmu', help='Select the PMU registry', required=False, type=int, choices=xrange(0, num_pmu))
    parser.add_argument('-cmask', '--cmask', help='Set the Counter umask', required=False, type=int)
    parser.add_argument('-inv', '--inv', help='Set the Invert counter mask', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-en', '--en', help='Set enable coutner', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-any', '--any', help='Set any thread', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-int', '--int', help='Set APIC interrupt enable', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-pc', '--pc', help='Set pin control', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-e', '--e', help='Set edge detect', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-os', '--os', help='Set operating system mode', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-user', '--user', help='Set user mode', required=False, type=str, choices=["on", "off"])
    parser.add_argument('-umask', '--umask', help='Set the umask', required=False, type=str)
    parser.add_argument('-event', '--event', help='Set the event', required=False, type=str)
    parser.add_argument('-r', '--reset', help='Reset PMU and fixed counters', required=False, action='store_true')
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        read_enable_fixed_pmu()
        read_conf_fixed()
        read_conf_pmu()
        read_perf_fixed()
        read_perf_pmu()
        sys.exit(1)
    elif args.reset:
        reset()
        sys.exit(1)

    if args.pmu is not None:
        if args.pmu >= num_pmu or args.pmu < 0:
            sys.stderr.write("[ERROR] PMU registries ranged from 1 to " + str(num_pmu) + "!\n")
            sys.exit(-1)
        if args.event is None or args.umask is None:
            sys.stderr.write("[ERROR] Need to be specify a PMU event and a PMU umask!\n")
            sys.exit(-1)
        
    if args.core is not None:
        core[args.core] = True
    else:
        core = [True] * num_core
    
    if args.enable_fix is True:
        fixed_counter = True
    if args.disable_fix is True:
        fixed_counter = False

    if args.enable_pmu is True:
        pmu_counter = True
    elif args.disable_pmu is True:
        pmu_counter = False

    if args.pmu is not None:
        pmu = args.pmu
    if args.umask is not None:
        if is_hex(args.umask):
            umask = int(args.umask, 16)
        elif is_int(args.umask):
            umask = int(args.umask, 10)
        else:
            sys.stderr.write("[WARNING] umask: " + args.umask + " is not a number!\n")
            exit(-1)
    if args.event is not None:
        if is_hex(args.event):
            event = int(args.event, 16)
        elif is_int(args.event):
            event = int(args.event, 10)
        else:
            sys.stderr.write("[WARNING] event: " + args.event + " is not a number!\n")
            exit(-1)

    # Apply configurations
    for c in range(num_core):
        if core[c] is True:
            # ENABLE FIXED
            if fixed_counter is not None:
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
            
            # ENABLE PMU
            if pmu_counter is not None:
                reg_perf_global_ctrl = read_msr(IA32_PERF_GLOBAL_CTRL, c)
                
                if pmu_counter is True:
                    reg_perf_global_ctrl = reg_perf_global_ctrl | CONF_ENABLE_PMU
                elif pmu_counter is False:
                    reg_perf_global_ctrl = reg_perf_global_ctrl & ~CONF_ENABLE_PMU
                
                write_msr(IA32_PERF_GLOBAL_CTRL, reg_perf_global_ctrl, c)

                if args.pmu is None:
                    for j in range(num_pmu):
                        reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[j], c)
                        reg_ia32_perfevtselx = reg_ia32_perfevtselx | CONF_EN_OS_USR
                        write_msr(IA32_PERFEVTSELX_ADDR[j], reg_ia32_perfevtselx, c)
                else:
                    reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[pmu], c)
                    reg_ia32_perfevtselx = reg_ia32_perfevtselx | CONF_EN_OS_USR
                    write_msr(IA32_PERFEVTSELX_ADDR[pmu], reg_ia32_perfevtselx, c)
            
            # UMASK
            if args.umask is not None:
                if args.pmu is None:
                    for j in range(num_pmu):
                        reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[j], c)
                        reg_ia32_perfevtselx = reg_ia32_perfevtselx | (umask << 8)
                        write_msr(IA32_PERFEVTSELX_ADDR[j], reg_ia32_perfevtselx, c)
                else:
                    reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[pmu], c)
                    reg_ia32_perfevtselx = reg_ia32_perfevtselx | (umask << 8)
                    write_msr(IA32_PERFEVTSELX_ADDR[pmu], reg_ia32_perfevtselx, c)

            # EVENT
            if args.event is not None:
                if args.pmu is None:
                    for j in range(num_pmu):
                        reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[j], c)
                        reg_ia32_perfevtselx = reg_ia32_perfevtselx | event
                        write_msr(IA32_PERFEVTSELX_ADDR[j], reg_ia32_perfevtselx, c)
                else:
                    reg_ia32_perfevtselx = read_msr(IA32_PERFEVTSELX_ADDR[pmu], c)
                    reg_ia32_perfevtselx = reg_ia32_perfevtselx | event
                    write_msr(IA32_PERFEVTSELX_ADDR[pmu], reg_ia32_perfevtselx, c)
