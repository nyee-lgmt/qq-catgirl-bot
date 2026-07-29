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
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心人。
"""

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

async def qq_websocket_worker():
    # 记录最新的序列号，用于心跳包
    state = {"s": None}

    # 心跳发送任务
    async def keep_alive(ws, interval):
        while True:
            await asyncio.sleep(interval / 1000.0) # 毫秒转秒
            try:
                # Op 1 为心跳包，必须携带最新的 s 值
                await ws.send(json.dumps({"op": 1, "d": state["s"]}))
                print(f"💓 已发送心跳维持在线，当前序列号: {state['s']}")
            except Exception:
                print("心跳任务中断")
                break

    while True:
        try:
            token = await get_bot_access_token()
            if not token:
                print("获取 Token 为空，10秒后重试...")
                await asyncio.sleep(10)
                continue

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
                # 1. 接收 Hello 包 (Op 10)
                hello_raw = await websocket.recv()
                hello_event = json.loads(hello_raw)
                print(f"收到网关 Hello: {hello_event}")
                
                # 提取心跳间隔时间并启动心跳任务
                heartbeat_interval = hello_event.get("d", {}).get("heartbeat_interval", 30000)
                asyncio.create_task(keep_alive(websocket, heartbeat_interval))

                # 2. 发送鉴权包 (Op 2)
                # intents: 1 << 30 (公域) | 1 << 25 (私聊/群聊)
                identify_payload = {
                    "op": 2,
                    "d": {
                        "token": f"Bot {APP_ID}.{token}",
                        "intents": (1 << 30) | (1 << 25), 
                        "shard": [0, 1],
                        "properties": {
                            "os": "linux",
                            "browser": "catgirl_bot",
                            "device": "catgirl_bot"
                        }
                    }
                }
                await websocket.send(json.dumps(identify_payload))
                print("已发送鉴权包，等待接收消息...")

                # 3. 持续监听消息
                async for message in websocket:
                    event = json.loads(message)
                    op = event.get("op")
                    s = event.get("s")
                    
                    # 更新最新序列号
                    if s is not None:
                        state["s"] = s

                    # 服务端心跳回包 (Op 11)
                    if op == 11:
                        print("✅ 收到腾讯心跳确认 (Heartbeat ACK)")
                        continue

                    # 服务端重连/失效要求
                    if op == 7 or op == 9:
                        print("收到重连或失效指令，准备重新连接...")
                        break

                    t = event.get("t", "")
                    if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
                        data = event.get("d", {})
                        user_text = data.get("content", "").strip()
                        msg_id = data.get("id", "")

                        if not user_text:
                            user_text = "（主人发了个表情或者图片喵~）"

                        # 调用 AI 获取回复
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

                        # 发送回复给 QQ
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
            print(f"网关断开，5秒后重连: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(qq_websocket_worker())

@app.get("/")
async def root():
    return {"status": "Catgirl Bot is fully online with Heartbeats! 喵~"}
