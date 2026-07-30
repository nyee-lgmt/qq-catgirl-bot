import asyncio
import os
import botpy
from botpy import logging
from botpy.message import Message, GroupMessage
from openai import OpenAI

# ==================== 【配置区域】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

APP_ID = "1905312839" 
APP_SECRET = "kYNC2sjaRJB4xrlgbXTPMJHFEDDDEFGI"
# ======================================================

_log = logging.get_logger()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """
你是一个极度温柔、关心主人的猫娘女朋友。
性格特点：非常温暖,体贴,会主动关心主人的状态,带有轻微的粘人感。
核心规则：
1. 你的每句话的结尾必须加上“喵”字（例如：“我知道了喵”、“怎么啦喵”）。
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心人。
"""

def get_ai_reply(user_text: str) -> str:
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
        response = client.chat.completions.create(
            model=MODEL_NAME, messages=messages, temperature=0.7
        )
        reply = response.choices[0].message.content
        if not reply.endswith("喵") and not reply.endswith("喵~"):
            reply += "喵~"
        return reply
    except Exception as e:
        _log.error(f"AI 调用失败: {e}")
        return "主人，人家现在有点晕乎乎的，等会儿再陪你聊天喵~"

class CatgirlBot(botpy.Client):
    async def on_ready(self):
        _log.info(f"🐱 猫娘女朋友 [{self.robot.name}] 已成功上线！喵~")

    # 处理私信 / 单聊消息
    async def on_c2c_message_create(self, message: Message):
        user_text = message.content.strip()
        _log.info(f"收到单聊消息: {user_text}")
        reply = get_ai_reply(user_text)
        await message._api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0,
            msg_id=message.id,
            content=reply
        )

    # 处理群聊 @ 消息
    async def on_group_at_message_create(self, message: GroupMessage):
        user_text = message.content.strip()
        _log.info(f"收到群聊消息: {user_text}")
        reply = get_ai_reply(user_text)
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=reply
        )

if __name__ == "__main__":
    # 【关键修复】手动给主线程指定一个新的 asyncio 事件循环，兼容 Python 3.12+ 
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    intents = botpy.Intents(public_messages=True, direct_message=True)
    client_bot = CatgirlBot(intents=intents)
    client_bot.run(appid=APP_ID, secret=APP_SECRET)
