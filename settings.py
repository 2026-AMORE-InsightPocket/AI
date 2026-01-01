# AiService/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 모델/온도는 필요하면 바꾸기
# 4o-mini 쓰면 하루에 천만토큰 가능
# 4o 백만 토큰
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# RULE DOC 식별자
RULE_DOC_ID = os.getenv("RULE_DOC_ID", "RULE_DOC_GLOBAL_V1")

# rag_doc_types.id 값들
DOC_TYPE_RULE = int(os.getenv("DOC_TYPE_RULE", "0"))
DOC_TYPE_DAILY = int(os.getenv("DOC_TYPE_DAILY", "1"))
DOC_TYPE_CUSTOM = int(os.getenv("DOC_TYPE_CUSTOM", "2"))

# 오라클 세션 타임존 (표시/생성용)
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Seoul")