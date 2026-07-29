import os
from fastapi import FastAPI, Request
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
# ======================================================

app = FastAPI()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 猫娘系统 Prompt 设定
SYSTEM_PROMPT = """
你是一个极度温柔、关心主人的猫娘女朋友。
性格特点：非常温暖、体贴、会主动关心主人的状态、带有轻微的粘人感。
核心规则：
1. 你的每句话的结尾必须加上“喵”字（例如：“我知道了喵”、“怎么啦喵”）。
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心人。
"""

@app.post("/")
async def qq_webhook(request: Request):
    body = await request.json()
    
    # 1. 应对 QQ 官方机器人的 URL 校验（验证你的网址是否有效）
    if "op" in body and body["op"] == 13:  # 或者是校验事件
        return body
        
    try:
        # 解析 QQ 官方机器人发来的用户聊天内容
        event_type = body.get("t", "")
        
        # 判断是否为群聊或私聊消息事件
        if event_type in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            message_data = body.get("d", {})
            user_text = message_data.get("content", "").strip()
            
            if not user_text:
                user_text = "（主人发了个表情或者图片喵~）"

            # 调用 DeepSeek 大模型
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
            
            # 确保每句话结尾带“喵”
            if not reply_text.endswith("喵") and not reply_text.endswith("喵~"):
                reply_text += "喵~"

            # 注意：QQ 官方机器人平台通常需要通过其 OpenAPI 接口发消息，
            # 但如果你使用的是极简 Webhook 模式，可以直接返回响应或由平台接管
            return {"content": reply_text}
            
    except Exception as e:
        print(f"错误: {e}")

    return {"status": "ok"}
