# /usr/local/bin/prlctl list --info "Windows 11" | grep -i ip

# Description:
#   IP Addresses: 10.211.55.3,fdb2:2c26:f4e4:0:c817:6f97:7498:cfc3,fe80::4ad0:7b22:2c54:75d4
#   Shared clipboard mode: on
#   Swipe from edges: off

import paramiko
import os
import subprocess
import re
from dotenv import load_dotenv

load_dotenv()


def get_parallels_ip(vm_name="Windows 11"):
    result = subprocess.run(
        ["/usr/local/bin/prlctl", "list", "--info", vm_name],
        capture_output=True,
        text=True,
    )
    match = re.search(r"IP Addresses:\s*([\d.]+)", result.stdout)
    if match:
        return match.group(1)
    raise RuntimeError("Parallels VM IP not found.")


prl_ip = get_parallels_ip()
print(f"PRL IP: {prl_ip}")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(
    prl_ip,
    username=os.getenv("PRL_USERNAME"),
    password=os.getenv("PRL_PASSWORD"),
    timeout=10,
    banner_timeout=10,
    auth_timeout=10,
)

# Write files
stdin, stdout, stderr = ssh.exec_command(
    "powershell -Command \"Set-Content -Path C:\\Users\\Public\\test.txt -Value 'Hello from Mac!' -Encoding UTF8\""
)
stdout.channel.recv_exit_status()
print("Done writing:", stdout.read().decode())
