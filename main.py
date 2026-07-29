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

# 获取 Access Token
async def get_access_token():
    async with httpx.AsyncClient() as client_http:
        try:
            res = await client_http.post(
                "https://bots.qq.com/app/get_access_token",
                json={"appId": APP_ID, "clientSecret": APP_SECRET}
            )
            data = res.json()
            return data.get("access_token")
        except Exception as e:
            print(f"获取 Token 失败: {e}")
            return None

# 后台异步长连接任务（自动连接腾讯网关接收消息）
async def run_bot_gateway():
    while True:
        try:
            token = await get_access_token()
            if not token:
                await asyncio.sleep(10)
                continue

            async with httpx.AsyncClient() as client_http:
                # 获取 WebSocket 网关地址
                gateway_res = await client_http.get(
                    "https://api.sgroup.qq.com/gateway",
                    headers={"Authorization": f"Bot {APP_ID}.{token}", "X-Union-App-Id": APP_ID}
                )
                gateway_data = gateway_res.json()
                ws_url = gateway_data.get("url")

            if not ws_url:
                await asyncio.sleep(10)
                continue

            print(f"正在连接 QQ 官方网关: {ws_url}")
            async with websockets.connect(ws_url) as websocket:
                # 1. 发送鉴权包
                payload = {
                    "op": 2,
                    "d": {
                        "token": f"Bot {APP_ID}.{token}",
                        "intents": 1 << 30, # 接收消息权限
                        "shard": [0, 1],
                        "properties": {}
                    }
                }
                await websocket.send(json.dumps(payload))

                # 2. 持续监听消息
                async for message in websocket:
                    event = json.loads(message)
                    op = event.get("op")
                    
                    # 保持心跳或处理事件
                    if op == 10:  # Hello 包，启动定时心跳
                        pass

                    t = event.get("t", "")
                    if t in ["GROUP_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"]:
                        data = event.get("d", {})
                        user_text = data.get("content", "").strip()
                        msg_id = data.get("id", "")
                        
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

                        # 回复消息
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
            print(f"网关连接断开，5秒后重连: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    # 启动后台网关任务
    asyncio.create_task(run_bot_gateway())

@app.get("/")
async def root():
    return {"status": "Catgirl Bot is running with Gateway!"}
