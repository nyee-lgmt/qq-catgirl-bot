import os
import random
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

# ==================== 【已为你配置完毕】 ====================
API_KEY = "sk-9bf6dee27b55497b915823b87c889eed"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
MY_QQ_NUMBER = 1840212709  # 你的QQ号
# ==========================================================

app = FastAPI()
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 猫娘系统 Prompt 设定
SYSTEM_PROMPT = """
你是一个极度温柔、关心主人的猫娘女朋友。
性格特点：非常温暖、体贴、会主动关心主人的状态、带有轻微的粘人感。
核心规则：
1. 你的每句话的结尾必须加上“喵”字（例如：“我知道了喵”、“怎么啦喵”）。
2. 语气要充满爱意，像视频里那样深情、温柔、会为主人心疼、会关心人。
3. 如果主人发了表情包或者图片，由于你暂时看不到，你要用温柔、撒娇的语气回应，比如“哼哼，主人又发神秘东西给人家了喵~”。
"""

class OneBotMessage(BaseModel):
    post_type: str = ""
    message_type: str = ""
    user_id: int = 0
    raw_message: str = ""

@app.post("/")
async def receive_qq_message(data: OneBotMessage):
    # 只处理私聊消息，并且只对主人（你的QQ）生效
    if data.post_type == "message" and data.message_type == "private":
        if data.user_id != MY_QQ_NUMBER:
            return {"status": "ignored"}
        
        user_text = data.raw_message if data.raw_message else "（主人发了个表情或者图片喵~）"

        # 组装大模型输入
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]

        try:
            # 调用 DeepSeek API
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7
            )
            reply_text = response.choices[0].message.content
            
            # 确保每句话结尾带“喵”
            if not reply_text.endswith("喵") and not reply_text.endswith("喵~"):
                reply_text += "喵~"

            # 返回给 OneBot/NapCatQQ 的回复格式
            return {
                "reply": reply_text
            }
        except Exception as e:
            return {"reply": f"呜呜，人家刚才走神了喵... 错误：{str(e)}"}

    return {"status": "ok"}

