import os
from openai import OpenAI
from utils.config import get_config_value

client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=get_config_value("ai_api_key"),
    base_url=get_config_value("ai_base_url"),
)

def analysic_inspection_result(result: str) -> str:
    """分析巡检结果，返回建议。"""
    completion = client.chat.completions.create(
        model=get_config_value("ai_model"),
        messages=[
            {"role": "system", "content": f"{get_config_value('ai_system_prompt')}"},
            {"role": "user", "content": f"巡检回显内容：{result}"}
        ],
        stream=True
    )
    suggestions = ""
    for chunk in completion:
        suggestions += chunk.choices[0].delta.content
    return suggestions

