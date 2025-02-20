from fastapi import APIRouter, status, Request, BackgroundTasks
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

'''
    This function will use paramiko to connect to the Windows Server and run the necessary commands to check the server health.

    The following health will be checked:
    - CPU Usage
    - Memory Usage
    - Disk Usage
    - Network Usage

    Function should handle error and return the error message to the return_url
    '''


async def check_server_health(payload: MonitorPayload):

    # Create an SSH client
    ssh = paramiko.SSHClient()
    # This will automatically add the server to the known_hosts file
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Get the server_ip, username and password from the payload
    settings_dict = {setting.label.lower(
    ): setting.default for setting in payload.settings}
    server_ip = settings_dict.get("server_ip")
    username = settings_dict.get("username")
    password = settings_dict.get("password")

    print(f"Connecting to {server_ip}")
    # Try to connect to the server and handle any errors
    try:
        ssh.connect(server_ip, username=username, password=password)
        print("Connected to the server")

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



    # Commands to check the server health
    commands = [
        "Get-WmiObject -class Win32_Processor | Select-Object -Property LoadPercentage",
        "Get-WmiObject -class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory, TotalVisibleMemorySize",
        "Get-WmiObject -class Win32_LogicalDisk | Select-Object -Property DeviceID, FreeSpace, Size",
        "Get-NetAdapter | Select-Object -Property Name, Status, LinkSpeed, ReceiveLinkSpeed, TransmitLinkSpeed"
    ]

    output_list = []
    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(
            f"powershell -Command \"{command}\"")
        output = stdout.read().decode().strip()
        print(output)

        # append output to a list
        output_list.append(output)

        # if "Win32_OperatingSystem" in command:
        #     lines = output.splitlines()
        #     print(lines)
        #     # free_memory = int(lines[1].split()[1])
        #     # total_memory = int(lines[1].split()[2])
        #     # memory_utilization = (
        #     #     (total_memory - free_memory) / total_memory) * 100
        #     # print(f"Memory Utilization: {memory_utilization:.2f}%")

    ssh.close()
    print("Connection closed")

    # Send the output to the return_url
    async with httpx.AsyncClient() as client:

        # convert the output list to a string
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
