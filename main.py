import os
import json
import httpx
from fastapi import FastAPI, Request
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

APP_ID = "1905312839"
APP_SECRET = "EPN9h2DAuQimbll0"
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

@app.get("/")
async def root():
    return {"status": "Catgirl Webhook Server is Live! 喵~"}

@app.post("/qq_webhook")
async def handle_qq_webhook(request: Request):
    try:
        body = await request.json()
        print(f"收到 QQ 回调数据: {body}")

        # 1. 处理腾讯开放平台校验请求 (Validation / Ping)
        if "op" in body and body["op"] == 13:
            return {"op": 13, "d": body.get("d")}

        # 2. 处理用户消息事件
        t = body.get("t", "")
        if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            data = body.get("d", {})
            user_text = data.get("content", "").strip()
            
            if not user_text:
                user_text = "（主人发了个表情或者图片喵~）"

            # 调用 DeepSeek 生成回复
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
            response = client.chat.completions.create(
                model=MODEL_NAME, messages=messages, temperature=0.7
            )
            reply_text = response.choices[0].message.content
            if not reply_text.endswith("喵") and not reply_text.endswith("喵~"):
                reply_text += "喵~"

            # 直接在 HTTP 响应中将结果返还给 QQ
            return {
                "content": reply_text
            }

        return {"status": "ok"}
    except Exception as e:
        print(f"处理 Webhook 发生错误: {e}")
        return {"status": "error", "message": str(e)}
