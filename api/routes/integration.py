from fastapi import APIRouter, status, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/integration")
async def integration(request: Request):
    base_url = str(request.base_url).rstrip("/")
    # telex_channel_webhook = "https://ping.telex.im/v1/webhooks/019519ce-8dd0-77d8-a5b4-20227ee0b485"
    payload = {
        "date": {
            "created_at": "2025-02-18",
            "updated_at": "2025-02-18"
        },
        "descriptions": {
            "app_name": "Windows Server Health Checker",
            "app_description": "Monitor the performance of a Windows Server",
            "app_logo": "https://i.imgur.com/bRoRB1Y.png",
            "app_url": f"{base_url}",
            "background_color": "#fff"
        },
        "is_active": False,
        "integration_type": "interval",
        "key_features": [
            "- Monitor the performance of a Windows Server",
            "- NB: This integration is only for Windows Servers"
            "- NB: Ensure that SSH is enabled on the Windows Server"
        ],
        "integration_category": "Monitoring & Logging",
        "author": "Chidubem Nwabuisi",
        "website": f"{base_url}",
        "settings": [
            {
                "label": "Server_IP",
                "type": "text",
                "required": True,
                "default": "",
            },
            {
                "label": "username",
                "type": "text",
                "required": True,
                "default": "",
            },
            {
                "label": "password",
                "type": "text",
                "required": True,
                "default": "",
            },
            {
                "label": "interval",
                "type": "text",
                "required": True,
                "default": "* * * * *",
            }
        ],
        "tick_url": f"{base_url}/api/v1/health",
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"data": payload}
    )
