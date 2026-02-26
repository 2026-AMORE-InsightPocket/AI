# AiService/chains/custom_report.py
"""
Custom Report Generation with RAG support

Generates custom reports based on user requests and attached data,
with context from recent daily reports for data-driven insights.
"""
from __future__ import annotations

from typing import List, Optional
import re
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from core.rag import RAGService
import settings


logger = logging.getLogger("insightpocket.custom_report")

def build_report_system_prompt(
    rule_md: str,
    daily_reports_context: Optional[str] = None,
) -> str:
    """
    Build system prompt for custom report generation

    Args:
        rule_md: RULE document content
        daily_reports_context: Context from recent daily reports

    Returns:
        System prompt text
    """
    rule_md = (rule_md or "").strip()

    base_prompt = f"""
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
"""

    # Add daily reports context if available
    if daily_reports_context:
        base_prompt += f"""

--- 참고: 최근 데일리 리포트 데이터 ---
{daily_reports_context}

위 데일리 리포트 데이터를 참고하여 시장 동향, 순위 변동, 리뷰 감성 등의 인사이트를 반영하라.
"""

    return base_prompt.strip()


def infer_title_from_md(md: str, fallback: str = "Custom Report") -> str:
    if not md:
        return fallback
    m = re.search(r"^\s*#\s+(.+)\s*$", md, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()[:120]
    return fallback


def generate_custom_report_md(
    *,
    lc_messages: List,
    rule_md: str,
    rag_service: Optional[RAGService] = None,
    use_rag: bool = True,
) -> str:
    """
    Generate custom report markdown

    Args:
        lc_messages: LangChain messages (user request + attached data)
        rule_md: RULE document content
        rag_service: RAG service instance (optional)
        use_rag: Whether to use RAG for recent daily reports

    Returns:
        Generated report in Markdown
    """
    # Build daily reports context if RAG is enabled
    daily_reports_context = None
    if use_rag and rag_service:
        try:
            # Extract user request from messages
            user_request = ""
            for msg in lc_messages:
                if hasattr(msg, "content"):
                    user_request = msg.content
                    break

            if user_request:
                daily_reports = rag_service.search_recent_daily_reports(
                    query=user_request,
                    top_k=3,
                )

                if daily_reports:
                    context_parts = []
                    for report in daily_reports:
                        title = report.get("title", "")
                        content = report.get("content", "")[:600]
                        report_date = report.get("report_date", "")
                        context_parts.append(
                            f"## {title} ({report_date})\n{content}..."
                        )

                    daily_reports_context = "\n\n".join(context_parts)
                    logger.info(
                        f"[CUSTOM_REPORT] Found {len(daily_reports)} recent daily reports for context"
                    )
        except Exception as e:
            logger.warning(f"[CUSTOM_REPORT] RAG search failed: {e}")

    # Build system prompt with daily reports context
    system = SystemMessage(
        content=build_report_system_prompt(rule_md, daily_reports_context)
    )

    # Generate report
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
    )

    resp = llm.invoke([system] + lc_messages)

    logger.info(f"[CUSTOM_REPORT] Generated report length: {len(resp.content)}")

    return str(resp.content).strip()
