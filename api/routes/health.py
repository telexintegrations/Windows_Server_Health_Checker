from fastapi import APIRouter, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import paramiko
import httpx


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

    # Implement the function here
    ssh = paramiko.SSHClient()
    # This will automatically add the server to the known_hosts file
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Extract the settings from the payload
    server_ip = payload.settings[0].default
    username = payload.settings[1].default
    password = payload.settings[2].default

    print(f"Connecting to {server_ip}")
    ssh.connect(server_ip, username=username, password=password)
    print("Connected to the server")

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
