import json
import hashlib
import hmac
from fastapi import FastAPI, Request
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

APP_SECRET = "EPN9h2DAuQimbll0"  # 腾讯机器人的 AppSecret
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

@app.api_route("/qq_webhook", methods=["GET", "POST"])
async def handle_qq_webhook(request: Request):
    try:
        # 处理 GET 请求
        if request.method == "GET":
            params = dict(request.query_params)
            plain_token = params.get("plain_token", "")
            return {"plain_token": plain_token, "signature": ""}

        # 处理 POST 请求
        try:
            body = await request.json()
        except Exception:
            body = {}

        print(f"收到 QQ 回调数据: {body}")

        # 核心：精准计算腾讯要求的签名结构
        if body.get("op") == 13 or "plain_token" in str(body):
            d = body.get("d", {})
            plain_token = d.get("plain_token", "")
            event_ts = d.get("event_ts", "")

            # 按照腾讯 HMAC-SHA256 标准计算签名
            msg = f"{event_ts}{plain_token}".encode('utf-8')
            signature = hmac.new(APP_SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()

            # 按照腾讯规范准确返回 plain_token 和计算好的 signature
            return {
                "plain_token": plain_token,
                "signature": signature
            }

        # 处理用户消息事件
        t = body.get("t", "")
        if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            data = body.get("d", {})
            user_text = data.get("content", "").strip()
            
            if not user_text:
                user_text = "（主人发了个表情或者图片喵~）"

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

            return {"content": reply_text}

        return {"status": "ok"}
    except Exception as e:
        print(f"处理 Webhook 异常: {e}")
        return {"status": "ok"}
