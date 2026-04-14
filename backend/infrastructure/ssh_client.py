"""
Infrastructure Layer - SSH Operations
Pure functions, no FastAPI dependency — testable without API or DB
"""

import json
import socket
from dataclasses import dataclass, asdict
from typing import Optional, Any


@dataclass
class ServerInfo:
    hostname: str
    ip: str
    os_type: str          # "linux" or "windows"
    os_version: Optional[str] = None
    cpu_model: Optional[str] = None
    cpu_count: Optional[int] = None
    memory_total: Optional[int] = None   # MB
    interfaces: Optional[list] = None    # [{name, ip, mac, pci_addr, pci_desc, speed}]
    error: Optional[str] = None


def check_online(ip: str, port: int = 22, timeout: int = 3) -> bool:
    """Check if a server is reachable via TCP (SSH port)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((ip, port)) == 0
    except socket.error:
        return False
    finally:
        sock.close()


def ping_icmp(ip: str, timeout: int = 3) -> bool:
    """Check if a server responds to ICMP ping."""
    import subprocess
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout * 1000), ip],
            capture_output=True, timeout=timeout + 1
        )
        return result.returncode == 0
    except Exception:
        return False


def get_server_status(ip: str, port: int = 22) -> dict:
    """Get server status: online + SSH port open."""
    online = check_online(ip, port=port)
    return {"ip": ip, "online": online, "ssh_open": online}


def _exec(ssh_client, cmd: str, timeout: int = 10) -> str:
    """Execute a command via paramiko SSHClient, return stdout."""
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()


def _pci_of_interface(ssh_client, iface: str) -> dict:
    """Get PCI address, description and speed for a network interface."""
    # Skip loopback and virtual interfaces
    if iface in ('lo',) or iface.startswith(('br-', 'docker', 'veth', 'virbr', 'tun', 'tap')):
        return {"pci_addr": None, "pci_desc": None, "speed": None}

    speed = ""
    speed_raw = _exec(ssh_client, f"cat /sys/class/net/{iface}/speed 2>/dev/null || echo ''").strip()
    if speed_raw and speed_raw.isdigit():
        speed = f"{speed_raw} Mb/s"

    # Get interface driver from sysfs
    driver_link = _exec(ssh_client, f"readlink /sys/class/net/{iface}/device/driver 2>/dev/null").strip()
    iface_driver = driver_link.split('/')[-1] if driver_link else ''

    # Build PCI addr -> (driver, description) map from lspci -nnk
    lspci_out = _exec(ssh_client, "lspci -nnk 2>/dev/null")
    import re
    pci_map = {}  # pci_addr -> {driver, desc}
    current_pci = None
    for line in lspci_out.split('\n'):
        line_s = line.lstrip()
        m = re.match(r'^([0-9a-f.:]+)\s+(.*)', line_s)
        if m:
            current_pci = m.group(1)
            rest = m.group(2)
            # Extract description after first [CATEGORY]:
            desc_m = re.match(r'.*?\]\s*:\s*(.*)', rest)
            desc = desc_m.group(1) if desc_m else rest
            # Remove subsystem [VENDOR:PRODUCT] and (rev ...)
            desc = re.sub(r'\s*\[[0-9a-f]{4}:[0-9a-f]{4}\].*', '', desc)
            desc = re.sub(r'\s*\(rev.*\)$', '', desc).strip()
            pci_map[current_pci] = {'desc': desc, 'driver': None}
        elif current_pci and 'Kernel driver in use:' in line:
            pci_map[current_pci]['driver'] = line.split('in use:')[-1].strip()
            current_pci = None

    # Try 1: driver name matches
    pci_addr = None
    pci_desc = None
    for addr, info in pci_map.items():
        if info['driver'] == iface_driver:
            pci_addr = addr
            pci_desc = info['desc']
            break

    # Try 2: fallback for ARM/RPi where drivers don't match lspci directly
    if not pci_addr:
        if iface_driver == 'macb' or iface == 'eth0':
            # Prefer Ethernet/Network first
            for addr, info in pci_map.items():
                kw = info['desc'].lower()
                if 'ethernet' in kw or 'network' in kw:
                    pci_addr = addr
                    pci_desc = info['desc']
                    break
            # Fallback: match bridge but skip host/PCI bridges (category 0604)
            if not pci_addr:
                for addr, info in pci_map.items():
                    kw = info['desc'].lower()
                    if 'bridge' in kw and 'pci bridge' not in kw and 'pcie bridge' not in kw:
                        pci_addr = addr
                        pci_desc = info['desc']
                        break
        elif iface_driver == 'brcmfmac' or iface == 'wlan0':
            for addr, info in pci_map.items():
                if any(kw in info['desc'].lower() for kw in ('network', 'wireless', 'wlan', 'wifi', '802.11')):
                    pci_addr = addr
                    pci_desc = info['desc']
                    break

    return {"pci_addr": pci_addr, "pci_desc": pci_desc, "speed": speed or None}


def _cpu_model_linux(ssh_client) -> str:
    """Get CPU model on Linux via dmidecode (most reliable on x86 servers)."""
    # dmidecode requires root, returns the processor brand string
    model = _exec(ssh_client, "dmidecode -s processor-version 2>/dev/null || echo ''").strip()
    if model:
        return model
    # Fallback: lscpu (works on most Linux distros)
    model = _exec(ssh_client, "lscpu | grep 'Model name' | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo ''").strip()
    if model:
        return model
    # Fallback: cpuinfo
    model = _exec(ssh_client, "cat /proc/cpuinfo | grep -m1 'model name' | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo ''").strip()
    return model


def fetch_server_info_linux(ssh_client) -> dict:
    """Fetch server info from Linux via paramiko transport."""
    try:
        hostname = _exec(ssh_client, "hostname")
        os_version = _exec(ssh_client, "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2")
        cpu_model = _cpu_model_linux(ssh_client)
        cpu_count_raw = _exec(ssh_client, "nproc 2>/dev/null || echo ''")
        cpu_count = int(cpu_count_raw) if cpu_count_raw.isdigit() else None
        mem_raw = _exec(ssh_client, "free -m 2>/dev/null | grep Mem | awk '{print $2}'")
        memory_total = int(mem_raw) if mem_raw.isdigit() else None

        # Interfaces via ip -j
        raw = _exec(ssh_client, "ip -j addr show 2>/dev/null")
        interfaces = []
        if raw:
            try:
                data = json.loads(raw)
                for i in data:
                    inet_addr = next(
                        (a["local"] for a in i.get("addr_info", []) if a.get("family") == "inet"),
                        None
                    )
                    iface_name = i.get("ifname", "")
                    pci = _pci_of_interface(ssh_client, iface_name)
                    interfaces.append({
                        "name": iface_name,
                        "ip": inet_addr,
                        "mac": i.get("address"),
                        "pci_addr": pci["pci_addr"],
                        "pci_desc": pci["pci_desc"],
                        "speed": pci["speed"],
                    })
            except json.JSONDecodeError:
                pass

        return {
            "hostname": hostname,
            "os_type": "linux",
            "os_version": os_version or None,
            "cpu_model": cpu_model or None,
            "cpu_count": cpu_count,
            "memory_total": memory_total,
            "interfaces": interfaces,
        }
    except Exception as e:
        return {
            "hostname": "", "os_type": "linux", "os_version": None,
            "cpu_model": None, "cpu_count": None, "memory_total": None, "interfaces": [],
            "error": str(e)
        }


def fetch_server_info_windows(ssh_client) -> dict:
    """Fetch server info from Windows via paramiko transport (PowerShell)."""
    try:
        hostname = _exec(ssh_client, 'powershell -Command "$env:COMPUTERNAME"')
        os_version = _exec(ssh_client, 'powershell -Command "(Get-WmiObject Win32_OperatingSystem).Caption"')
        cpu_model = _exec(ssh_client, 'powershell -Command "(Get-WmiObject Win32_Processor).Name"')
        cpu_raw = _exec(ssh_client, 'powershell -Command "(Get-WmiObject Win32_Processor).NumberOfCores"')
        cpu_count = int(cpu_raw) if cpu_raw.isdigit() else None
        mem_raw = _exec(ssh_client, 'powershell -Command "[math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1MB)"')
        memory_total = int(mem_raw) if mem_raw.isdigit() else None

        # Interfaces
        raw = _exec(ssh_client, 'powershell -Command "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress | ConvertTo-Json"')
        interfaces = []
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                for i in data:
                    interfaces.append({
                        "name": i.get("InterfaceAlias", ""),
                        "ip": i.get("IPAddress", ""),
                        "mac": None,
                        "pci_addr": None,
                        "pci_desc": None,
                        "speed": None,
                    })
            except json.JSONDecodeError:
                pass

        return {
            "hostname": hostname,
            "os_type": "windows",
            "os_version": os_version or None,
            "cpu_model": cpu_model or None,
            "cpu_count": cpu_count,
            "memory_total": memory_total,
            "interfaces": interfaces,
        }
    except Exception as e:
        return {
            "hostname": "", "os_type": "windows", "os_version": None,
            "cpu_model": None, "cpu_count": None, "memory_total": None, "interfaces": [],
            "error": str(e)
        }


def get_server_info_via_ssh(
    ip: str,
    username: str,
    password: Optional[str] = None,
    key_file: Optional[str] = None,
    port: int = 22,
) -> ServerInfo:
    """
    Connect via SSH and fetch server info.
    Returns ServerInfo dataclass.
    """
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            ip,
            port=port,
            username=username,
            password=password,
            key_filename=key_file,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )

        # Detect OS
        os_raw = _exec(client, "uname -s 2>/dev/null || echo Windows")
        is_windows = "windows" in os_raw.lower() or os_raw == "Windows"

        data = fetch_server_info_windows(client) if is_windows else fetch_server_info_linux(client)

        return ServerInfo(
            hostname=data.get("hostname", ""),
            ip=ip,
            os_type=data.get("os_type", "unknown"),
            os_version=data.get("os_version"),
            cpu_model=data.get("cpu_model"),
            cpu_count=data.get("cpu_count"),
            memory_total=data.get("memory_total"),
            interfaces=data.get("interfaces"),
            error=data.get("error"),
        )

    except Exception as e:
        return ServerInfo(hostname="", ip=ip, os_type="unknown", error=str(e))

    finally:
        client.close()
