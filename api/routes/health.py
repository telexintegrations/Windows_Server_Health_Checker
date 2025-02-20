from fastapi import APIRouter, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import paramiko
import httpx
import socket

# Define the models for the request and response payloads


class Setting(BaseModel):
    label: str
    type: str
    required: bool
    default: str


class MonitorPayload(BaseModel):
    channel_id: str
    return_url: str
    settings: List[Setting]


router = APIRouter()


async def check_server_health(payload: MonitorPayload):
    # Create an SSH client
    ssh = paramiko.SSHClient()
    # This will automatically add the server to the known_hosts file
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Get the server_ip, username and password from the payload
    settings_dict = {setting.label.lower(): setting.default for setting in payload.settings}
    server_ip = settings_dict.get("server_ip")
    username = settings_dict.get("username")
    password = settings_dict.get("password")

    print(f"Connecting to {server_ip}")
    # Try to connect to the server and handle any errors
    try:
        ssh.connect(server_ip, username=username, password=password)
        print("Connected to the server")

        # Commands to check the server health
        commands = [
            "Get-WmiObject -class Win32_Processor | Select-Object -Property LoadPercentage",
            "Get-WmiObject -class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory, TotalVisibleMemorySize",
            "Get-WmiObject -class Win32_LogicalDisk | Select-Object -Property DeviceID, FreeSpace, Size",
            "Get-NetAdapter | Select-Object -Property Name, Status, LinkSpeed, ReceiveLinkSpeed, TransmitLinkSpeed",
            # "Get-Counter -Counter \"\\Network Interface(*)\\Packets Sent/sec\", \"\\Network Interface(*)\\Packets Received/sec\"",
        ]

        output_dict = {}
        for command in commands:
            stdin, stdout, stderr = ssh.exec_command(
                f"powershell -Command \"{command}\"")
            output = stdout.read().decode().strip()
            print(output)

            if "Win32_Processor" in command:
                output_dict["CPU Load Percentage"] = f"{output.splitlines()[2].strip()}%"
            elif "Win32_OperatingSystem" in command:
                lines = output.splitlines()[2].split()
                free_memory_kb = int(lines[0])
                total_memory_kb = int(lines[1])
                output_dict["Free Physical Memory"] = f"{free_memory_kb / 1024:.2f} MB"
                output_dict["Total Visible Memory Size"] = f"{total_memory_kb / 1024:.2f} MB"
            elif "Win32_LogicalDisk" in command:
                disks = []
                for line in output.splitlines()[2:]:
                    parts = line.split()
                    free_space_bytes = int(parts[1])
                    size_bytes = int(parts[2])
                    disks.append({
                        "DeviceID": parts[0],
                        "FreeSpace": f"{free_space_bytes / (1024 ** 3):.2f} GB",
                        "Size": f"{size_bytes / (1024 ** 3):.2f} GB"
                    })
                output_dict["Logical Disks"] = disks
            elif "Get-NetAdapter" in command:
                lines = output.splitlines()[:]
                output_dict["Network Adapter"] = {
                    "Name": lines[0].split(":")[1].strip(),
                    "Status": lines[1].split(":")[1].strip(),
                    "LinkSpeed": lines[2].split(":")[1].strip(),
                    "ReceiveLinkSpeed": f"{int(lines[3].split(':')[1].strip()) / 1_000_000_000:.2f} Gbps",
                    "TransmitLinkSpeed": f"{int(lines[4].split(':')[1].strip()) / 1_000_000_000:.2f} Gbps"
                }
            # elif "Get-Counter" in command:
            #     lines = output.splitlines()[2:]
            #     packets_sent = 0
            #     packets_received = 0
            #     for line in lines:
            #         parts = line.split()
            #         if "Packets Sent/sec" in parts[0]:
            #             packets_sent += int(parts[1])
            #         elif "Packets Received/sec" in parts[0]:
            #             packets_received += int(parts[1])
            #     output_dict["Network Packets"] = {
            #         "Packets Sent/sec": packets_sent,
            #         "Packets Received/sec": packets_received
            #     }
            # elif "Get-Counter" in command:
            #     lines = output.splitlines()[2:]
            #     print("Network traffic: " + str(lines))
            #     network_traffic = {}
            #     for i in range(0, len(lines), 3):
            #         interface_name = lines[i].split("\\")[2].split("(")[1].split(")")[0]
            #         packets_sent = lines[i+1].split(":")[1].strip()
            #         packets_received = lines[i+2].split(":")[1].strip()
            #         network_traffic[interface_name] = {
            #             "Packets Sent/sec": packets_sent,
            #             "Packets Received/sec": packets_received
            #         }
            #     output_dict["Network Traffic"] = network_traffic


        ssh.close()
        print("Connection closed")

    # Handle authentication errors
    except paramiko.AuthenticationException as e:
        print("Authentication failed")
        # send error message to the telex return_url
        async with httpx.AsyncClient() as client:
            data = {
                "message": "Authentication failed. Please check the username and password",
                "username": "Windows Server Health Checker",
                "event_name": "Server Health Check",
                "status": "error"
            }
            response = await client.post(payload.return_url, json=data)
            print(response.status_code)
            print(response.json())
            return

    # Handle connection Timeout errors
    except (TimeoutError, socket.timeout) as e:
        print("Connection timed out to Windows server")
        # send error message to the telex return_url
        async with httpx.AsyncClient() as client:
            data = {
                "message": "Connection timed out. Check the server IP and ensure that SSH is enabled",
                "username": "Windows Server Health Checker",
                "event_name": "Server Health Check",
                "status": "error"
            }
            response = await client.post(payload.return_url, json=data)
            print(response.status_code)
            print(response.json())
            return

    # Send the output to the return_url
    async with httpx.AsyncClient() as client:

        # convert the output list to a string
        output_list = []
        for key, value in output_dict.items():
            if isinstance(value, list):
                output_list.append(f"{key}:")
                for item in value:
                    output_list.append(f"    {item}")
            else:
                output_list.append(f"{key}: {value}")

        print(output_list)

        output_list = "\n".join(output for output in output_list)

        data = {
            "message": output_list,
            "username": "Windows Server Health Checker",
            "event_name": "Server Health Check",
            "status": "success"
        }

        response = await client.post(payload.return_url, json=data)
        print(response.status_code)
        print(response.json())

# This is the endpoint that telex will call to check server health. Process will be handled in the background


@router.post("/health")
async def check_health(payload: MonitorPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(check_server_health, payload)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "accepted"})
