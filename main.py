import json
from fastapi import FastAPI, Request, Response
from openai import OpenAI
from cryptography.hazmat.primitives.asymmetric import ed25519

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

# 根据 APP_SECRET 生成 Ed25519 验证公钥
def get_ed25519_public_key(secret: str):
    seed = secret
    while len(seed) < 32:
        seed += secret
    seed_bytes = seed[:32].encode('utf-8')
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
    return private_key.public_key()

PUB_KEY = get_ed25519_public_key(APP_SECRET)

@app.get("/")
async def root():
    return {"status": "Catgirl Webhook Server is Live! 喵~"}

@app.post("/qq_webhook")
async def handle_qq_webhook(request: Request):
    try:
        body_bytes = await request.body()
        
        # 1. 获取腾讯请求头中的签名参数
        signature_hex = request.headers.get("X-Signature-Ed25519", "")
        timestamp = request.headers.get("X-Signature-Timestamp", "")

        # 2. 如果存在签名头，进行 Ed25519 验签
        if signature_hex and timestamp:
            try:
                sig_bytes = bytes.fromhex(signature_hex)
                msg = timestamp.encode('utf-8') + body_bytes
                PUB_KEY.verify(sig_bytes, msg)
            except Exception as sig_err:
                print(f"❌ 签名验证失败: {sig_err}")
                return Response(status_code=401, content="Unauthorized")

        body = json.loads(body_bytes.decode('utf-8'))
        print(f"✅ 校验通过，收到数据: {body}")

        # 3. 处理腾讯校验/Ping事件
        if body.get("op") == 13:
            return {"op": 13, "d": body.get("d")}

        # 4. 处理用户发送的消息
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

            return {"content": reply_text}

        return {"status": "ok"}
    except Exception as e:
        print(f"处理 Webhook 异常: {e}")
        return {"status": "error", "message": str(e)}
