#!/usr/bin/env python
# coding: utf-8

# In[19]:


import requests
import json
import urllib3


# Proxmox API Credentials
PROXMOX_HOST = "192.168.0.100"
USERNAME = "root@pam"  # Root user (or API user)
PASSWORD = "denpen7172"
NODE = "proxmox"

# Thresholds
CPU_THRESHOLD = 80  # % usage
RAM_THRESHOLD = 80  # % usage

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Authenticate and get ticket/token
def get_proxmox_ticket():
    url = f"https://{PROXMOX_HOST}:8006/api2/json/access/ticket"
    payload = {"username": USERNAME, "password": PASSWORD}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=payload, headers=headers, verify=False)

    if response.status_code == 200:
        data = response.json()
        return data["data"]["ticket"], data["data"]["CSRFPreventionToken"]
    else:
        print(f"❌ Failed to authenticate: {response.text}")
        return None, None

# Get VM usage stats
def get_vm_usage(vm_id, ticket):
    url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/{NODE}/qemu/{vm_id}/status/current"
    headers = {"Cookie": f"PVEAuthCookie={ticket}"}

    response = requests.get(url, headers=headers, verify=False)

    if response.status_code == 200:
        data = response.json()
        if "data" in data:
            print("✅ API Response:", json.dumps(data["data"], indent=4))  # Print full response
            return data["data"]
        else:
            print(f"❌ No usage data found for VM {vm_id}.")
            print("🔍 API Response:", response.text)
            return None
    else:
        print(f"❌ Failed to fetch usage for VM {vm_id}. HTTP Status: {response.status_code}")
        print("🔍 Response:", response.text)
        return None

# Main script execution
ticket, csrf_token = get_proxmox_ticket()
if ticket:
    vm_data = get_vm_usage(100, ticket)
    if vm_data:
        print("✅ Successfully retrieved VM usage stats!")


def get_vms(ticket):
    # Get the list of Proxmox nodes first
    nodes_url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes"
    headers = {"Cookie": f"PVEAuthCookie={ticket}"}

    nodes_response = requests.get(nodes_url, headers=headers, verify=False)
    if nodes_response.status_code == 200:
        nodes_data = nodes_response.json()
        if "data" in nodes_data and nodes_data["data"]:
            node_name = nodes_data["data"][0]["node"]  # Get the first available node
            print(f"✅ Using node: {node_name}")  # Print selected node
            
            # Now, get the VMs for that node
            url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/{node_name}/qemu"
            response = requests.get(url, headers=headers, verify=False)

            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    return data["data"]
                else:
                    print("❌ No VMs found on the node.")
                    return []
            else:
                print(f"❌ Failed to fetch VM list. HTTP Status: {response.status_code}")
                print("🔍 Response:", response.text)  # Print full response for debugging
                return []
        else:
            print("❌ No nodes found in Proxmox.")
            return []
    else:
        print(f"❌ Failed to fetch Proxmox nodes. HTTP Status: {nodes_response.status_code}")
        print("🔍 Response:", nodes_response.text)  # Print full response for debugging
        return []

# Scale VM if needed
def scale_vm(vm_id, vm_name, cpu, max_cpu, ram, max_ram, ticket, csrf_token):
    if cpu > CPU_THRESHOLD:
        new_cpus = min(max_cpu + 1, 8)  # Limit to 8 CPUs max
        print(f"⚡ Scaling up CPU for VM {vm_name} ({vm_id}) to {new_cpus} CPUs...")
        scale_url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/{NODE}/qemu/{vm_id}/config"
        headers = {"Cookie": f"PVEAuthCookie={ticket}", "CSRFPreventionToken": csrf_token}
        payload = {"cores": new_cpus}
        requests.put(scale_url, headers=headers, data=payload, verify=False)

    if ram > RAM_THRESHOLD:
        new_ram = min(max_ram + 1024, 8192)  # Limit to 8GB max
        print(f"⚡ Scaling up RAM for VM {vm_name} ({vm_id}) to {new_ram} MB...")
        scale_url = f"https://{PROXMOX_HOST}:8006/api2/json/nodes/{NODE}/qemu/{vm_id}/config"
        headers = {"Cookie": f"PVEAuthCookie={ticket}", "CSRFPreventionToken": csrf_token}
        payload = {"memory": new_ram}
        requests.put(scale_url, headers=headers, data=payload, verify=False)

# Main script execution
if __name__ == "__main__":
    ticket, csrf_token = get_proxmox_ticket()
    vms = get_vms(ticket)

    for vm in vms:
        vm_id = vm["vmid"]
        vm_name = vm["name"]
        stats = get_vm_usage(vm_id, ticket)

        if stats:
            cpu_usage = stats["cpu"] * 100  # Convert to percentage
            ram_usage = (stats["mem"] / stats["maxmem"]) * 100  # Convert to percentage

            print(f"🔍 VM: {vm_name} | CPU: {cpu_usage:.2f}% | RAM: {ram_usage:.2f}%")

            #scale_vm(vm_id, vm_name, cpu_usage, vm["cores"], ram_usage, vm["maxmem"] // 1024, ticket, csrf_token)
            scale_vm(vm_id, vm_name, cpu_usage, stats["cpus"], ram_usage, stats["maxmem"] // 1024, ticket, csrf_token)


    print("✅ Scaling check complete.")


# In[ ]:




