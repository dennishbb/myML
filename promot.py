#!/usr/bin/env python
# coding: utf-8

# In[10]:


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
PROXMOX_PASSWORD = "denpen7172"
PROMETHEUS_URL = "http://192.168.0.34:9090/api/v1/query"

# VM Details
VMS = {
    "192.168.0.95": 100,  # VM ID for first VM
    "192.168.0.96": 101   # VM ID for second VM
}

CPU_THRESHOLD = 85  # CPU usage percentage threshold to scale

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

def scale_vm(vm_id, current_cpu, ticket, csrf_token):
    """Scale the VM CPU if needed."""
    # Increase CPU cores by 1
    new_cpu = int(current_cpu) + 1
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
            time.sleep(60)  # Wait before retrying
            continue

        for vm_ip, vm_id in VMS.items():
            cpu_usage = get_cpu_usage(vm_ip)

            if cpu_usage is not None:
                logging.info(f"VM {vm_id} CPU Usage: {cpu_usage:.2f}%")

                if cpu_usage > CPU_THRESHOLD:
                    logging.warning(f"High CPU detected on VM {vm_id} ({cpu_usage:.2f}%). Scaling up...")
                    scale_vm(vm_id, cpu_usage, ticket, csrf_token)
                else:
                    logging.info(f"VM {vm_id} CPU is normal.")
            else:
                logging.error(f"Failed to fetch CPU usage for VM {vm_id}")

        logging.info("Scaling check complete.")
        time.sleep(300)  # Runs every 5 minutes

if __name__ == "__main__":
    main()

