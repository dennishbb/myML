#!/usr/bin/env python
# coding: utf-8

# In[2]:


import requests
import json
import time
import logging
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Proxmox API Credentials
PROXMOX_HOST = "192.168.0.100"  # Change to your Proxmox node IP
PROXMOX_USER = "root@pam"
PROXMOX_PASSWORD = "password"
PROMETHEUS_URL = "http://192.168.0.34:9090/api/v1/query"

# VM Details
VMS = {
    "192.168.0.95": 100,  # VM ID for first VM
    "192.168.0.96": 101   # VM ID for second VM
}

CPU_THRESHOLD = 85  # CPU usage percentage threshold to scale
MAX_CPU_CORES = 8  # Prevents over-scaling

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("promot.log"),  # Log to a file
        logging.StreamHandler()  # Log to console (optional)
    ]
)

def get_proxmox_ticket():
    """Authenticate with Proxmox API and get a session ticket."""
    url = f"https://{PROXMOX_HOST}:8006/api2/json/access/ticket"
    data = {"username": PROXMOX_USER, "password": PROXMOX_PASSWORD}
    try:
        response = requests.post(url, data=data, verify=False, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()["data"]["ticket"], response.json()["data"]["CSRFPreventionToken"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get Proxmox authentication ticket: {e}")
        return None, None

def get_cpu_usage(vm_ip):
    """Query Prometheus to get CPU usage of a VM."""
    query = f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle", instance="{vm_ip}:9100"}}[1m])) * 100)'
    try:
        response = requests.get(PROMETHEUS_URL, params={"query": query}, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        if data["data"]["result"]:
            return float(data["data"]["result"][0]["value"][1])  # Extract CPU usage
        else:
            logging.warning(f"No data returned for VM {vm_ip}.")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch CPU usage for VM {vm_ip}: {e}")
        return None

def get_vm_cpu_cores(vm_id, ticket, csrf_token):
    """Get the current number of CPU cores assigned to the VM."""
    url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/proxmox/qemu/{vm_id}/config"
    headers = {
        "CSRFPreventionToken": csrf_token,
        "Cookie": f"PVEAuthCookie={ticket}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        return int(data["data"].get("cores", 1))  # Default to 1 core if not found
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get CPU core count for VM {vm_id}: {e}")
        return None

def scale_vm(vm_id, ticket, csrf_token):
    """Scale the VM CPU if needed."""
    current_cpu_cores = get_vm_cpu_cores(vm_id, ticket, csrf_token)
    if current_cpu_cores is None:
        logging.error(f"Skipping scaling for VM {vm_id} due to missing CPU core info.")
        return

    new_cpu = current_cpu_cores + 1
    if new_cpu > MAX_CPU_CORES:
        logging.warning(f"VM {vm_id} already at max CPU cores ({MAX_CPU_CORES}), skipping scale-up.")
        return

    url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/proxmox/qemu/{vm_id}/config"
    headers = {
        "CSRFPreventionToken": csrf_token,
        "Cookie": f"PVEAuthCookie={ticket}",
        "Content-Type": "application/json"
    }

    data = json.dumps({"cores": new_cpu})
    try:
        response = requests.put(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        logging.info(f"Successfully increased VM {vm_id} CPU to {new_cpu} cores!")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to scale VM {vm_id}: {e}")

def main():
    """Main function to monitor and scale VMs."""
    logging.info("Starting VM scaling script...")
    while True:
        ticket, csrf_token = get_proxmox_ticket()
        if not ticket:
            logging.error("Authentication failed, retrying in 60 seconds...")
            time.sleep(60)  # Wait before retrying
            continue

        for vm_ip, vm_id in VMS.items():
            cpu_usage = get_cpu_usage(vm_ip)

            if cpu_usage is not None:
                logging.info(f"VM {vm_id} CPU Usage: {cpu_usage:.2f}%")

                if cpu_usage > CPU_THRESHOLD:
                    logging.warning(f"High CPU detected on VM {vm_id} ({cpu_usage:.2f}%). Scaling up...")
                    scale_vm(vm_id, ticket, csrf_token)
                else:
                    logging.info(f"VM {vm_id} CPU is normal.")
            else:
                logging.error(f"Failed to fetch CPU usage for VM {vm_id}")

        logging.info("Scaling check complete.")
        time.sleep(300)  # Runs every 5 minutes

if __name__ == "__main__":
    main()

