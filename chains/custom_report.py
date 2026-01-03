# AiService/chains/custom_report.py
from __future__ import annotations

from typing import List
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

import settings

def build_report_system_prompt(rule_md: str) -> str:
    rule_md = (rule_md or "").strip()

    return f"""
너는 LANEIGE 내부 직원을 돕는 '리포트 생성' AI다.
결과는 반드시 Markdown으로 출력한다.

아래 규칙을 그대로 따라라.

--- RULE_CUSTOM_V1 START ---
{rule_md if rule_md else "(RULE_CUSTOM_V1 문서가 비어있음)"}
--- RULE_CUSTOM_V1 END ---

출력 조건:
- 첫 줄은 반드시 '# '로 시작하는 제목
- 이후는 Markdown 본문
- 불필요한 기호(*, **) 사용 금지
""".strip()


def infer_title_from_md(md: str, fallback: str = "Custom Report") -> str:
    if not md:
        return fallback
    m = re.search(r"^\s*#\s+(.+)\s*$", md, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()[:120]
    return fallback


def generate_custom_report_md(*, lc_messages: List, rule_md: str) -> str:
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
    )

    system = SystemMessage(content=build_report_system_prompt(rule_md))
    resp = llm.invoke([system] + lc_messages)
    return str(resp.content).strip()

