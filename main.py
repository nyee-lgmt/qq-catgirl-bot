import json
from fastapi import FastAPI, Request
from openai import OpenAI
from cryptography.hazmat.primitives.asymmetric import ed25519

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

APP_SECRET = "EPN9h2DAuQimbll0"  # 请核对是否和 QQ 开放平台后台的 AppSecret 完全一致
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

# 根据 AppSecret 生成 32 字节 seed 并导出 Ed25519 私钥
def get_ed25519_private_key(secret: str):
    secret_bytes = secret.encode('utf-8')
    if len(secret_bytes) < 32:
        seed = secret_bytes.ljust(32, b'\x00')
    else:
        seed = secret_bytes[:32]
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)

PRIV_KEY = get_ed25519_private_key(APP_SECRET)

# 响应腾讯探活 HEAD / GET 请求，防止报 405
@app.head("/")
@app.get("/")
async def root():
    return {"status": "Catgirl Webhook Server is Live! 喵~"}

@app.api_route("/qq_webhook", methods=["GET", "POST", "HEAD"])
async def handle_qq_webhook(request: Request):
    try:
        # 处理 HEAD 探活
        if request.method == "HEAD":
            return {"status": "ok"}

        # 处理 GET 请求
        if request.method == "GET":
            params = dict(request.query_params)
            return {"plain_token": params.get("plain_token", ""), "signature": ""}

        # 处理 POST 请求
        body_bytes = await request.body()
        timestamp = request.headers.get("X-Signature-Timestamp", "")

        try:
            body = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            body = {}

        print(f"👉 收到 QQ 开放平台推送: {body}")

        # 腾讯 op: 13 签名校验
        if body.get("op") == 13 or "plain_token" in str(body):
            d = body.get("d", {})
            plain_token = d.get("plain_token", "")

            # 签名逻辑：msg = timestamp + body
            msg = timestamp.encode('utf-8') + body_bytes
            signature = PRIV_KEY.sign(msg).hex()

            print(f"✅ 计算并返回签名: {signature}")

            return {
                "plain_token": plain_token,
                "signature": signature
            }

        # 处理聊天消息
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
        print(f"❌ 处理 Webhook 异常: {e}")
        return {"status": "ok"}
