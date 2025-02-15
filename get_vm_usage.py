import sys
from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
import atexit

def get_vm_resource_usage(vcenter, username, password, vm_name):
    si = SmartConnectNoSSL(host=vcenter, user=username, pwd=password)
    atexit.register(Disconnect, si)
    
    content = si.RetrieveContent()
    vm = None

    for datacenter in content.rootFolder.childEntity:
        for vm_folder in datacenter.vmFolder.childEntity:
            if vm_folder.name == vm_name:
                vm = vm_folder
                break

    if not vm:
        print("0\n0")
        return

    cpu_usage = vm.summary.quickStats.overallCpuUsage
    ram_usage = vm.summary.quickStats.guestMemoryUsage

    print(cpu_usage)
    print(ram_usage)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: get_vm_usage.py <vcenter> <username> <password> <vm_name>")
        sys.exit(1)

    get_vm_resource_usage(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
