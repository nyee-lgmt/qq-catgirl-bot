import json
from fastapi import FastAPI, Request
from openai import OpenAI
from cryptography.hazmat.primitives.asymmetric import ed25519

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# 请在此处填写 QQ 开放平台的 AppSecret
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

# 严格按照腾讯文档：将 Secret 生成 32 字节 seed 并创建 Ed25519 私钥
def get_private_key(secret_str: str):
    try:
        # 如果 Secret 是 64 位 Hex 字符串
        seed = bytes.fromhex(secret_str)
    except Exception:
        # 如果是普通文本，转为 UTF-8 编码并用 0 补齐或截取至 32 字节
        b = secret_str.encode('utf-8')
        if len(b) < 32:
            seed = b.ljust(32, b'\x00')
        else:
            seed = b[:32]
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)

PRIV_KEY = get_private_key(APP_SECRET)

@app.head("/")
@app.get("/")
async def root():
    return {"status": "Catgirl Webhook Server is Live! 喵~"}

@app.api_route("/qq_webhook", methods=["GET", "POST", "HEAD"])
async def handle_qq_webhook(request: Request):
    try:
        if request.method == "HEAD":
            return {"status": "ok"}

        if request.method == "GET":
            params = dict(request.query_params)
            return {"plain_token": params.get("plain_token", ""), "signature": ""}

        # 获取原始 Body 字节流与请求头
        body_bytes = await request.body()
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        if not timestamp:
            timestamp = request.headers.get("x-signature-timestamp", "")

        body_str = body_bytes.decode('utf-8')
        try:
            body_json = json.loads(body_str)
        except Exception:
            body_json = {}

        print(f"👉 收到 QQ 消息: {body_str}")

        # 1. 腾讯 op: 13 或签名校验事件
        if body_json.get("op") == 13 or "plain_token" in body_str:
            d = body_json.get("d", {})
            plain_token = d.get("plain_token", "")

            # 官方计算公式：msg = timestamp.encode() + body_bytes
            msg_to_sign = timestamp.encode('utf-8') + body_bytes
            sig_bytes = PRIV_KEY.sign(msg_to_sign)
            signature = sig_bytes.hex()

            print(f"✅ 计算官方签名成功: {signature}")

            return {
                "plain_token": plain_token,
                "signature": signature
            }

        # 2. 处理聊天消息
        t = body_json.get("t", "")
        if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            data = body_json.get("d", {})
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
        print(f"❌ 运行异常: {e}")
        return {"status": "ok"}
