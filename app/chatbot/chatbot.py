from app.chatbot.config import OPENAI_API_KEY, SYSTEM_PROMPT_TEXT
from openai import OpenAI
from fastapi import HTTPException
import json
from app.chatbot.chatbot_functions import *

# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "fetch_issues_by_author",
#             "description": "Belirli bir kullanıcının issue'larını getirir.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "author_username": {"type": "string"}
#                 },
#                 "required": ["author_username"]
#             }
#         }
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "fetch_issue_details",
#             "description": "Belirli bir issue'nun detaylarını getirir.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "issue_iid": {"type": "integer"}
#                 },
#                 "required": ["issue_iid"]
#             }
#         }
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "fetch_merge_requests",
#             "description": "MR'ları listeler.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "state": {"type": "string", "enum": ["opened", "closed", "locked", "merged", "all"]},
#                     "author_username": {"type": "string"},
#                     "assignee_username": {"type": "string"},
#                     "reviewer_username": {"type": "string"},
#                     "search": {"type": "string"}
#                 }
#             }
#         }
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "fetch_merge_request_details",
#             "description": "Belirli bir MR detayını getirir.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "mr_iid": {"type": "integer"}
#                 },
#                 "required": ["mr_iid"]
#             }
#         }
#     }
# ]
# FUNCTION_MAP = {
#     "fetch_issues_by_author": fetch_issues_by_author,
#     "fetch_issue_details": fetch_issue_details,
#     "fetch_merge_requests": fetch_merge_requests,
#     "fetch_merge_request_details": fetch_merge_request_details
# }

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_issues",
            "description": "Belirtilen proje için issue listesini getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["opened", "closed"],
                        "description": "Issue durumu"
                    },
                    "author_username": {
                        "type": "string",
                        "description": "Issue yaratan kullanıcı adı"
                    },
                    "assignee_username": {
                        "type": "string",
                        "description": "Issue atanan kullanıcı adı"
                    },
                    "search": {
                        "type": "string",
                        "description": "Başlık/description içinde aranacak metin"
                    }
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_merge_requests",
            "description": "MR'ları listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["opened", "closed", "locked", "merged", "all"]},
                    "author_username": {"type": "string"},
                    "assignee_username": {"type": "string"},
                    "reviewer_username": {"type": "string"},
                    "search": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_merge_request_details",
            "description": "Belirli bir MR detayını getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mr_iid": {"type": "integer"}
                },
                "required": ["mr_iid"]
            }
        }
    }
]

FUNCTION_MAP = {
    "fetch_issues": fetch_issues,
    "fetch_merge_requests": fetch_merge_requests,
    "fetch_merge_request_details": fetch_merge_request_details
}



openai_client = OpenAI(api_key=OPENAI_API_KEY)

def create_tool_call_history_unit(response):
    if not response.tool_calls:
        raise ValueError("create_tool_call'a verdigin response tool call içermiyor")

    tool_call_msg_template = {
        "role": "assistant",
        "content": [],
        "tool_calls": [

        ]
    }

    for tool_call in response.tool_calls:
        log = {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments
            }
        }
        tool_call_msg_template["tool_calls"].append(log)

    return tool_call_msg_template


def create_tool_response_history_unit(tool_call_id: str, tool_response):
    tool_response_template = {
        "role": "tool",
        "content": [
            {
                "type": "text",
                "text": json.dumps(tool_response)
            }
        ],
        "tool_call_id": tool_call_id
    }
    return tool_response_template


async def get_chatbot_response(user_message_content: str, message_history, project_path,gitlab_token):
    # ----------------------------------------------
    # TEMPLATES FOR HISTORY MANAGEMENT:
    system_msg_history_unit = {"role": "system", "content": [{"type": "text", "text":SYSTEM_PROMPT_TEXT}]}
    user_msg_history_unit = {"role": "user", "content": [{"type": "text", "text":user_message_content}]}
    assistant_msg_history_unit = {"role": "assistant", "content": [{"type": "text", "text":""}]}
    # -------------------------------------------


    if not message_history:
        message_history.append(system_msg_history_unit)
    message_history.append(user_msg_history_unit)



    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=message_history,
        tools=TOOLS,
    )
    """
    Choice(finish_reason='stop', index=0, logprobs=None, 
    message=ChatCompletionMessage(content='Merhaba! GitLab projenizle ilgili bir sorunuz var mı? Size yardımcı olmaktan memnuniyet duyarım.',
     refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=None))
    ChatCompletionMessage(content='Merhaba! GitLab projenizle ilgili bir sorunuz var mı? Size yardımcı olmaktan memnuniyet duyarım.',
    refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=None)  """

    response = completion.choices[0].message


    if response.tool_calls:
        tool_call_history_unit = create_tool_call_history_unit(response)
        message_history.append(tool_call_history_unit)
        for tool_call in response.tool_calls:
            function_name = tool_call.function.name
            args_str = tool_call.function.arguments

            args_dict = json.loads(args_str)  # JSON string → dict

            args_dict["full_path"] = project_path # BBBBBBBBBBBBBBBBBBBBB
            args_dict["gitlab_token"] = gitlab_token #CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
            if function_name in FUNCTION_MAP:
                function_response = await FUNCTION_MAP[function_name](**args_dict)
                tool_response_history_unit = create_tool_response_history_unit(tool_call.id, function_response)
                message_history.append(tool_response_history_unit)
            else:
                raise ValueError(f"Fonksiyon bulunamadı: {function_name}")
        # print(message_history) #AAAAAAAAAA

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=message_history,
            tools=TOOLS,
        )
        response = completion.choices[0].message
        response_text = response.content
        assistant_msg_history_unit["content"][0]["text"] = response_text
        message_history.append(assistant_msg_history_unit)
    else:

        response_text = response.content
        assistant_msg_history_unit["content"][0]["text"] = response_text
        message_history.append(assistant_msg_history_unit)






    return response_text

# def allocate_history(message_history, role, content):
    # system_msg = {"role": "system", "content": SYSTEM_PROMPT_TEXT}
    # user_msg = {"role": "user", "content": prompt}
    # AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA TOOL DA EKLENCEK
