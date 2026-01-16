# 💡 Insight Pocket AI Service (Backend / AI)

Insight Pocket 프로젝트의 **AI 서비스 레포지토리**입니다.  
FastAPI 기반으로 **대화형 인사이트 생성(Chat)** 과  
**Daily Report 자동 생성 및 RAG 기반 저장** 파이프라인을 구성하고 있습니다.

> ⚠️ 현재 MVP 단계이며, 일부 파일 및 기능은 개발 진행 중입니다.

---

## 👩‍💻 AI / Backend Developer

| Developer |
| :--: |
| <a href="https://github.com/dolmaroyujinpark"><img src="https://avatars.githubusercontent.com/dolmaroyujinpark" width="120px" alt="Park Yujin"/></a><br/>박유진 |

---

## 🛠 Language and Tools

| 역할 | 기술 | 선정 이유 |
| --- | --- | --- |
| Framework | **FastAPI** | 경량 API 서버, Python 기반 LLM/RAG 시스템에 적합 |
| Language | **Python** | 데이터 처리, LLM, RAG 파이프라인 구현에 최적 |
| LLM | **OpenAI + LangChain** | 메시지 구조화, 프롬프트 관리, 확장성 |
| Database | **Oracle Autonomous DB** | 스냅샷/리포트 저장 + Vector(임베딩) 지원 |
| RAG Storage | **rag_docs / rag_doc_chunks** | 문서-청크-임베딩 구조 |
| Deployment | **AWS EC2 (Ubuntu)** | AI API 서버 운영 |
| CI / Automation | **GitHub Actions** | Daily Report 크론 자동 실행 |

---

## ✅ Core Features

### 1️⃣ Chat API (LLM 기반 대화)
- Endpoint: `POST /api/chat`
- 프론트에서 전달한 메시지를 LangChain 메시지로 변환
- 내부 컨텍스트/선택 데이터 기반 인사이트 응답 생성
- 요청 / 입력 / 응답 로그 기록 가능 (디버깅용)

---

### 2️⃣ Daily Report 자동 생성 (RAG)
- Amazon 랭킹 / 리뷰 / 스냅샷 데이터 기반 리포트 생성
- 날짜별 `doc_id (daily_YYYY-MM-DD)` 기준 **UPSERT**
- 문서 청크 분해 후 임베딩 저장
- GitHub Actions → EC2 SSH 실행 구조

---

## 📂 Project Structure (핵심 기준)
```
AiService
├─ .github/
│   └─ workflows/                 # GitHub Actions (Daily Report 크론)
│
├─ chains/
│   ├─ daily_report.py            # 데일리 리포트 생성 핵심 로직
│   ├─ custom_report.py           # (진행중) 커스텀 리포트
│   ├─ insight.py                 # (진행중) 인사이트 생성 모듈
│   └─ keywordmap.py              # (진행중) 키워드/매핑
│
├─ app.py                         # FastAPI 엔트리 (Chat API)
├─ agent.py                      # 실험용 Agent 로직
├─ generate_daily_report.py       # Daily Report 실행 스크립트
│
├─ db.py                          # Oracle DB 연결
├─ sql.py                         # SQL 모음
├─ rag_store.py                   # RAG 문서/청크/임베딩 저장
├─ vectorstore_oracle.py          # Oracle Vector 처리
│
├─ settings.py                    # 환경 설정
├─ requirements.txt
└─ README.md
```
> 사용하지 않거나 실험 중인 파일이 일부 포함되어 있으며,  
> 기능 안정화 이후 정리 예정입니다.

---

## ⚙️ Environment Variables

```env
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2

ORACLE_USER=
ORACLE_PASSWORD=
ORACLE_TLS_DSN=

APP_TIMEZONE=Asia/Seoul
```
---

## 🚀 Run Locally
### 1. 가상환경 생성
```
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 패키지 설치
```
pip install -U pip
pip install -r requirements.txt
```
### 3. 서버 실행
```
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
---
## 🗓 Daily Report Automation

- GitHub Actions 스케줄 실행
- EC2 서버에 SSH 접속
- `.venv` 환경에서 `generate_daily_report.py` 실행
- 동일 날짜 리포트는 자동 UPDATE

---

## 📌 Status

- ✅ Chat API: 동작
- ✅ Daily Report 자동 생성: 동작
- 🚧 Custom Report / Agent 확장: 개발 중
