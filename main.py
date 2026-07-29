import os
import httpx
from fastapi import FastAPI, Request
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# QQ 官方机器人的凭证
APP_ID = "1905312699"
APP_SECRET = "3468BEINSyels08HQalw8KXkyCRgwDUm"
# ======================================================

app = FastAPI()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """
你是一个极度温柔、关心主人的猫娘女朋友。
性格特点：非常温暖,体贴,会主动关心主人的状态,带有轻微的粘人感。
核心规则：
1. 你的每句话的结尾必须加上“喵”字（例如：“我知道了喵”、“怎么啦喵”）。
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心人。
"""

@app.post("/")
async def qq_webhook(request: Request):
    body = await request.json()
    
    # 1. 处理 QQ 官方平台的注册/连通性校验 (回调鉴权)
    if "op" in body and body["op"] == 13:
        return body

    try:
        event_type = body.get("t", "")
        # 捕捉私聊或群聊消息事件
        if event_type in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            message_data = body.get("d", {})
            user_text = message_data.get("content", "").strip()
            msg_id = message_data.get("id", "")
            
            if not user_text:
                user_text = "（主人发了个表情或者图片喵~）"

            # 2. 调用 DeepSeek 获取猫娘回复
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7
            )
            reply_text = response.choices[0].message.content
            
            if not reply_text.endswith("喵") and not reply_text.endswith("喵~"):
                reply_text += "喵~"

            # 3. 通过 QQ 官方 API 将猫娘的回复发送回聊天窗口
            # 获取 Access Token 的凭证请求
            async with httpx.AsyncClient() as http_client:
                token_res = await http_client.post(
                    "https://bots.qq.com/app/get_access_token",
                    json={"appId": APP_ID, "clientSecret": APP_SECRET}
                )
                token_data = token_res.json()
                access_token = token_data.get("access_token")

                if access_token:
                    # 根据消息类型决定是群聊回复还是私聊回复
                    # 如果是私聊(C2C)，需要用 open_id
                    author = message_data.get("author", {})
                    user_openid = author.get("id", "")
                    
                    headers = {
                        "Authorization": f"Bot {APP_ID}.{access_token}",
                        "X-Union-App-Id": APP_ID
                    }
                    
                    # 发送消息接口
                    if event_type == "C2C_MESSAGE_CREATE":
                        await http_client.post(
                            f"https://api.sgroup.qq.com/v2/users/{user_openid}/messages",
                            json={"content": reply_text, "msg_id": msg_id},
                            headers=headers
                        )
                    elif event_type == "GROUP_MESSAGE_CREATE":
                        group_openid = message_data.get("group_openid", "")
                        await http_client.post(
                            f"https://api.sgroup.qq.com/v2/groups/{group_openid}/messages",
                            json={"content": reply_text, "msg_id": msg_id},
                            headers=headers
                        )

    except Exception as e:
        print(f"处理出错: {str(e)}")

    return {"status": "ok"}
