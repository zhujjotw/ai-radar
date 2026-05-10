"""Chat router: SSE streaming endpoint for AI chat."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.auth import AuthUser, get_current_user
from app.services.ai_chat import stream_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    enable_web_search: bool = False


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    async def event_generator():
        async for event in stream_chat(req.message, req.enable_web_search):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
