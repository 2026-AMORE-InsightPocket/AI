#RAG 검색, 툴콜 기반 채팅

from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.documents import Document

from vectorstore_oracle import search_reports


@tool
def rag_search_daily_reports(query: str) -> str:
    """일일 랭킹 리포트(Vector DB)에 대해 유사도 검색을 수행하고 핵심 근거를 반환한다."""
    docs: List[Document] = search_reports(query, k=6)
    if not docs:
        return "검색 결과 없음"

    lines = []
    for i, d in enumerate(docs, 1):
        meta = d.metadata
        lines.append(
            f"[{i}] date={meta.get('report_date')} type={meta.get('doc_type')} "
            f"brand={meta.get('brand')} category={meta.get('category')} :: {d.page_content}"
        )
    return "\n\n".join(lines)


def run_chat(question: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    # 가장 단순한 “도구 호출 + 답변” 루프
    tools = [rag_search_daily_reports]
    # agent가 검색엔진을 쓸 수 있다
    llm_with_tools = llm.bind_tools(tools)

    msg = llm_with_tools.invoke(
        [
            {
                "role": "system",
                "content": "너는 라네즈 직원으로서, 아마존 뷰티 랭킹/리뷰 리포트를 분석하는 어시스턴트다. "
                           "필요하면 반드시 도구를 호출해 근거를 확인한 뒤 답하라."
            },
            {"role": "user", "content": question},
        ]
    )

    # 모델이 tool call을 하면, 그 결과를 다시 넣어 최종 답변 생성
    if getattr(msg, "tool_calls", None):
        tool_outputs = []
        for tc in msg.tool_calls:
            if tc["name"] == "rag_search_daily_reports":
                out = rag_search_daily_reports.invoke(tc["args"])
                tool_outputs.append({"role": "tool", "tool_call_id": tc["id"], "content": out})

        final = llm.invoke(
            [
                {"role": "system", "content": "도구 결과를 근거로, 요약+비교+액션아이템까지 간결하게 답하라."},
                {"role": "user", "content": question},
                msg,
                *tool_outputs,
            ]
        )
        return final.content

    return msg.content