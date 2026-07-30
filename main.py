import json
from fastapi import FastAPI, Request
from openai import OpenAI
from cryptography.hazmat.primitives.asymmetric import ed25519

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# 已经将你最新生成的密钥硬编码进去了
APP_SECRET = "kYNC2sjaRJB4xrlgbXTPMJHFEDDDEFGI"
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

# 严格遵照 QQ 官方文档的 Seed 算法生成 Ed25519 私钥
def get_qq_ed25519_private_key(bot_secret: str):
    seed = bot_secret
    # 如果 Seed 长度不够 32 字节，重复拼贴自身直至达到 32 字节
    while len(seed) < 32:
        seed += bot_secret
    seed_bytes = seed[:32].encode('utf-8')
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)

PRIV_KEY = get_qq_ed25519_private_key(APP_SECRET)

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

        body_bytes = await request.body()
        try:
            body_json = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            body_json = {}

        print(f"👉 收到 QQ 推送数据: {body_json}")

        # 处理校验事件 (op: 13 或者包含 d.plain_token)
        d = body_json.get("d", {})
        plain_token = d.get("plain_token")
        event_ts = d.get("event_ts")

        if body_json.get("op") == 13 or plain_token:
            # 官方签名算法：msg = event_ts + plain_token
            msg_str = f"{event_ts}{plain_token}"
            msg_bytes = msg_str.encode('utf-8')

            # 使用 Ed25519 签名并转为 hex 字符串
            sig_bytes = PRIV_KEY.sign(msg_bytes)
            signature = sig_bytes.hex()

            print(f"✅ 严格对齐官方规范，生成签名成功: {signature}")

            return {
                "plain_token": plain_token,
                "signature": signature
            }

        # 处理聊天消息
        t = body_json.get("t", "")
        if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
            user_text = d.get("content", "").strip()

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
