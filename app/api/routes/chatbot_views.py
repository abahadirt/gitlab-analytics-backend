from fastapi import APIRouter, Query, Path, Request, HTTPException
from pydantic import BaseModel
from app.chatbot.chatbot_before_chat import get_full_path_from_id_rest
from app.chatbot import chatbot

from app.settings import settings

router = APIRouter()

from typing import Dict, Tuple, List
history_dict: Dict[Tuple[str, str], List[str]] = {}

class MessageRequest(BaseModel):
    message: str

@router.post("/chat/message/{project_id}")
async def chat(request: Request, MessageRequest: MessageRequest, project_id: int):
    global history_dict
    data = await request.json()
    user_message = MessageRequest.message

    gitlab_token = request.cookies.get("gitlab_token") or settings.GITLAB_DEFAULT_TOKEN
    """
    eğer kullanıcı gitlab token girmediyse ve bu yüzden chatbot projeye ulaşamıyorsa bu durumu
    kullanıcıya açıklayan bir response dönülebilir.
    """

    project_path = await get_full_path_from_id_rest(project_id,gitlab_token)

    session_id = request.cookies.get("sessionid")

    context_key = (session_id, project_path)

    inital_history = history_dict.setdefault(context_key, [])

    bot_response= await chatbot.get_chatbot_response(user_message,inital_history,project_path,gitlab_token)


    return [{"response": bot_response}]
