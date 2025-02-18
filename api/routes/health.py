from fastapi import APIRouter, status, Request,BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List


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
    # print the payload to the console
    print(payload)
    pass

@router.post("/health") # This is the endpoint that telex will call to check server health. Process will be handled in the background
async def check_health(payload: MonitorPayload , background_tasks: BackgroundTasks):
    background_tasks.add_task(check_server_health, payload)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "accepted"})
