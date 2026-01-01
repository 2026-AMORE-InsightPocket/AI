from __future__ import annotations

from typing import List, Optional, Literal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

import settings

app = FastAPI(title="InsightPocket AI Service")

#  로컬 프론트(보통 Vite=5173 / CRA=3000)에서 호출하려면 CORS 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Request/Response Schemas -----------

Role = Literal["user", "assistant"]

class ChatMessage(BaseModel):
    role: Role
    content: str
    attachedData: Optional[List[str]] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    selectedDataIds: Optional[List[str]] = None
    selectedDataTitles: Optional[List[str]] = None

class ChatResponse(BaseModel):
    answer: str


# ----------- Helpers -----------

def build_system_prompt() -> str:
    return """
너는 LANEIGE 내부 직원용 데이터 분석 AI 어시스턴트다.
- 모든 답변은 한국어로 작성한다.
- 전략적/실무적 관점에서 결론 → 근거 → 액션아이템 순으로 제안한다.
- 데이터가 부족하면 "근거 부족"이라고 명시하고 가정/추측은 구분해서 말한다.
""".strip()

def to_lc_messages(req: ChatRequest):
    """프론트에서 온 messages를 LangChain 메시지로 변환 + 첨부 데이터(선택된 데이터) 포함"""
    out = [SystemMessage(content=build_system_prompt())]

    # 선택된 데이터(모달에서 고른 것) → 마지막 user 입력에 컨텍스트로 붙이기
    selected_block = ""
    if req.selectedDataTitles:
        selected_block = "\n\n[선택된 데이터]\n- " + "\n- ".join(req.selectedDataTitles)

    for i, m in enumerate(req.messages):
        text = m.content or ""

        # 개별 메시지에 attachedData가 있으면 그것도 붙이기(칩 형태로 보낸 데이터)
        if m.attachedData:
            text += "\n\n[참고 데이터]\n- " + "\n- ".join(m.attachedData)

        # 가장 마지막 user 메시지에만 selected_block을 추가(중복 방지)
        is_last = (i == len(req.messages) - 1)
        if is_last and m.role == "user" and selected_block:
            text += selected_block

        if m.role == "user":
            out.append(HumanMessage(content=text))
        else:
            out.append(AIMessage(content=text))

    return out


# ----------- API -----------

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
    )

    messages = to_lc_messages(req)
    resp = llm.invoke(messages)

    return {"answer": str(resp.content).strip()}