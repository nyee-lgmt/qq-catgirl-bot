import os
import json
import asyncio
import websockets
import httpx
from fastapi import FastAPI
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# 你的机器人最新凭证
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
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心คน。
"""

# 按照官方标准的 Client Credentials 方式获取 Access Token
async def get_bot_access_token():
    async with httpx.AsyncClient() as client_http:
        try:
            res = await client_http.post(
                "https://bots.qq.com/app/get_access_token",
                json={"appId": APP_ID, "clientSecret": APP_SECRET},
                timeout=10.0
            )
            data = res.json()
            return data.get("access_token")
        except Exception as e:
            print(f"获取官方 Token 异常: {e}")
            return None

# WebSocket 长期在线网关任务
async def qq_websocket_worker():
    while True:
        try:
            token = await get_bot_access_token()
            if not token:
                print("获取 Token 为空，10秒后重试...")
                await asyncio.sleep(10)
                continue

            # 请求官方网关地址
            async with httpx.AsyncClient() as client_http:
                gateway_res = await client_http.get(
                    "https://api.sgroup.qq.com/gateway",
                    headers={
                        "Authorization": f"Bot {APP_ID}.{token}",
                        "X-Union-App-Id": APP_ID
                    },
                    timeout=10.0
                )
                gateway_data = gateway_res.json()
                ws_url = gateway_data.get("url")

            if not ws_url:
                print("获取网关地址失败，10秒后重试...")
                await asyncio.sleep(10)
                continue

            print(f"正在连接腾讯官方 WebSocket: {ws_url}")
            async with websockets.connect(ws_url) as websocket:
                # 接收来自网关的 Hello 包 (Op 10)
                hello_raw = await websocket.recv()
                hello_event = json.loads(hello_raw)
                print(f"收到网关 Hello: {hello_event}")

                # 按照官方文档发送鉴权包 (Op 2 Identify)
                # intents = 1 << 30 (公域消息事件) 或者根据实际需要调整
                identify_payload = {
                    "op": 2,
                    "d": {
                        "token": f"Bot {APP_ID}.{token}",
                        "intents": 1 << 30, 
                        "shard": [0, 1],
                        "properties": {
                            "os": "linux",
                            "browser": "my_catgirl_bot",
                            "device": "my_catgirl_bot"
                        }
                    }
                }
                await websocket.send(json.dumps(identify_payload))
                print("已发送鉴权包，等待接收消息...")

                # 保持循环监听消息与心跳
                async for message in websocket:
                    event = json.loads(message)
                    op = event.get("op")
                    
                    # 如果是服务端发来的 Reconnect 或 Invalid Session，跳出重连
                    if op == 7 or op == 9:
                        print("收到重连或失效指令，准备重新连接...")
                        break

                    t = event.get("t", "")
                    # 捕捉私聊(C2C)或群聊(GROUP)消息事件
                    if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
                        data = event.get("d", {})
                        user_text = data.get("content", "").strip()
                        msg_id = data.get("id", "")
                        
                        if not user_text:
                            user_text = "（主人发了个表情或者图片喵~）"

                        # 调用 DeepSeek AI 生成回复
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

                        # 通过标准 OpenAPI 把回复发回 QQ 窗口
                        async with httpx.AsyncClient() as client_http:
                            headers = {
                                "Authorization": f"Bot {APP_ID}.{token}",
                                "X-Union-App-Id": APP_ID
                            }
                            if t == "C2C_MESSAGE_CREATE":
                                user_openid = data.get("author", {}).get("id", "")
                                await client_http.post(
                                    f"https://api.sgroup.qq.com/v2/users/{user_openid}/messages",
                                    json={"content": reply_text, "msg_id": msg_id}, headers=headers
                                )
                            elif t == "GROUP_MESSAGE_CREATE":
                                group_openid = data.get("group_openid", "")
                                await client_http.post(
                                    f"https://api.sgroup.qq.com/v2/groups/{group_openid}/messages",
                                    json={"content": reply_text, "msg_id": msg_id}, headers=headers
                                 )

        except Exception as e:
            print(f"网关捕获到异常错误，5秒后自动尝试重连: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    # 启动后台异步任务，让猫娘的灵魂在云端常驻
    asyncio.create_task(qq_websocket_worker())

@app.get("/")
async def root():
    return {"status": "Catgirl Bot is fully connected via Official WebSocket Spec!"}
