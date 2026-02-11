# RAG (Retrieval-Augmented Generation) 설계 문서

## 📋 목차

1. [개요](#개요)
2. [RAG가 필요한 이유](#rag가-필요한-이유)
3. [아키텍처](#아키텍처)
4. [구현 세부사항](#구현-세부사항)
5. [사용 시나리오](#사용-시나리오)
6. [성능 최적화](#성능-최적화)
7. [향후 개선 방향](#향후-개선-방향)

---

## 개요

InsightPocket의 RAG 시스템은 **과거에 생성된 레포트와 인사이트를 검색하여 현재 질문에 대한 답변을 향상**시키는 시스템입니다.

### 핵심 목표

1. **일관성**: 과거 분석과 일관된 인사이트 제공
2. **정확성**: 실제 데이터에 기반한 답변
3. **효율성**: 빠른 검색과 응답 생성
4. **확장성**: 레포트가 늘어나도 성능 유지

---

## RAG가 필요한 이유

### 문제점 (Before RAG)

❌ **컨텍스트 부족**
- LLM이 과거 인사이트를 모름
- 일관성 없는 분석 결과
- 동일한 질문에 다른 답변

❌ **데이터 활용 불가**
- 생성한 레포트가 재활용되지 않음
- 매번 처음부터 분석
- 누적된 지식 활용 불가

❌ **트렌드 분석 한계**
- 과거 데이터 비교 어려움
- 장기 트렌드 파악 불가
- 시계열 분석 제한

### 해결 (After RAG)

✅ **컨텍스트 풍부**
- 과거 레포트 자동 검색
- 일관된 분석 프레임워크
- 누적된 인사이트 활용

✅ **데이터 재활용**
- 모든 레포트가 검색 가능
- 유사 케이스 참조
- 학습 효과 증가

✅ **트렌드 분석 가능**
- 과거 데이터와 자동 비교
- 장기 트렌드 파악
- 시계열 인사이트 제공

---

## 아키텍처

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                      1. Document Ingestion                  │
│                                                              │
│  Daily Report / Custom Report                               │
│         │                                                    │
│         ├─→ Markdown Text                                   │
│         ├─→ Chunk (1200 chars, 120 overlap)                 │
│         ├─→ Generate Embeddings (OpenAI)                    │
│         └─→ Store in Vector DB (Oracle)                     │
│                                                              │
│  rag_docs: {doc_id, title, body_md, doc_type_id, date}     │
│  rag_doc_chunks: {chunk_id, doc_id, content, embedding}    │
└─────────────────────────────────────────────────────────────┘

                           ▼

┌─────────────────────────────────────────────────────────────┐
│                      2. Query Processing                     │
│                                                              │
│  User Query: "지난 2주 Lip Sleeping Mask 순위 변화는?"     │
│         │                                                    │
│         ├─→ Intent Analysis                                 │
│         │   - needs_historical_data: True                   │
│         │   - time_range: "last_2_weeks"                    │
│         │                                                    │
│         ├─→ Generate Query Embedding                        │
│         │                                                    │
│         └─→ Vector Search                                   │
│             - Similarity: COSINE distance                   │
│             - Filters: doc_type=DAILY, date range           │
│             - Top-K: 5 results                              │
└─────────────────────────────────────────────────────────────┘

                           ▼

┌─────────────────────────────────────────────────────────────┐
│                    3. Context Building                       │
│                                                              │
│  [USER_ATTACHED_DATA]                                       │
│  - 현재 사용자가 첨부한 데이터                                │
│                                                              │
│  [RELEVANT_PAST_INSIGHTS]                                   │
│  - 2026-02-08 Daily Report: "Lip Sleeping Mask ranked..."  │
│  - 2026-02-05 Daily Report: "Ranking improved by..."       │
│  - 2026-02-01 Daily Report: "Product showed..."            │
│                                                              │
│  → Combined Context (max 3000 tokens)                       │
└─────────────────────────────────────────────────────────────┘

                           ▼

┌─────────────────────────────────────────────────────────────┐
│                      4. LLM Generation                       │
│                                                              │
│  System Prompt + Context + User Query                       │
│         │                                                    │
│         └─→ GPT-4o-mini                                     │
│             - 과거 데이터 기반 트렌드 분석                    │
│             - 일관된 톤과 형식                                │
│             - 실제 데이터 인용                                │
└─────────────────────────────────────────────────────────────┘

                           ▼

┌─────────────────────────────────────────────────────────────┐
│                      5. Response                             │
│                                                              │
│  "Lip Sleeping Mask는 지난 2주간 지속적인 상승세를            │
│   보였습니다. 2월 1일 #12에서 시작해 2월 8일 #8까지           │
│   4단계 상승했으며, 이는 주로 긍정적인 리뷰 증가와            │
│   프로모션 효과로 분석됩니다."                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 구현 세부사항

### 1. Embedding Generation

**모델**: `text-embedding-3-small`

**이유**:
- 고품질 임베딩 (1536 dimensions)
- 낮은 비용 ($0.02 / 1M tokens)
- 빠른 속도

**코드**:
```python
# core/embeddings.py
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=settings.OPENAI_API_KEY
)

# 단일 텍스트
vector = embeddings.embed_query("text")

# 여러 문서
vectors = embeddings.embed_documents(["doc1", "doc2"])
```

### 2. Chunking Strategy

**파라미터**:
- `max_chars`: 1200 (약 300 tokens)
- `overlap`: 120 (10% 오버랩)

**이유**:
- LLM 컨텍스트 창 효율적 활용
- 문맥 유지를 위한 오버랩
- 검색 정확도 향상

**알고리즘**:
```python
# core/vectorstore.py
def _chunk_markdown(md: str, max_chars=1200, overlap=120):
    # 1. 문단 단위로 분할 (\\n\\n)
    paras = re.split(r"\\n{2,}", md)

    # 2. 버퍼에 누적
    # 3. max_chars 초과 시 플러시
    # 4. overlap만큼 이전 내용 유지
```

### 3. Vector Search

**메트릭**: COSINE distance

**필터링**:
- Document Type (RULE / DAILY / CUSTOM)
- Date Range (report_date)
- Similarity Threshold (기본 0.7)

**Oracle SQL**:
```sql
SELECT
    c.content,
    c.doc_id,
    d.title,
    VECTOR_DISTANCE(c.embedding, :query_vec, COSINE) as distance
FROM rag_doc_chunks c
JOIN rag_docs d ON c.doc_id = d.doc_id
WHERE d.doc_type_id IN (:doc_type_ids)
  AND d.report_date BETWEEN :date_from AND :date_to
ORDER BY distance ASC
FETCH FIRST :top_k ROWS ONLY
```

### 4. Context Building

**전략**: Hybrid Context

1. **User Attached Data** (최우선)
   - 사용자가 Pocket에서 선택한 데이터
   - 항상 컨텍스트에 포함

2. **Past Reports** (RAG)
   - 유사도 기반 검색
   - 날짜 범위 필터링
   - Top-K 개수 제한

3. **Real-time Data** (필요 시)
   - DB 직접 쿼리
   - 최신 랭킹/리뷰 데이터

**컨텍스트 크기 관리**:
```python
# core/rag.py
MAX_CONTEXT_CHUNKS = 3  # 최대 3개 청크
CHUNK_PREVIEW_LEN = 500  # 청크당 500자 미리보기
```

---

## 사용 시나리오

### 시나리오 1: 트렌드 질문

**User**: "지난 한 달 Water Sleeping Mask 순위 추세는?"

**Process**:
1. Query Intent Analysis
   - `needs_historical_data`: True
   - `time_range`: "last_month"
   - `mentioned_products`: ["Water Sleeping Mask"]

2. RAG Search
   - Doc Type: DAILY
   - Date Range: 2026-01-12 ~ 2026-02-12
   - Query: "Water Sleeping Mask 순위"
   - Results: 5개 Daily Report chunks

3. Context
   ```
   [RELEVANT_PAST_INSIGHTS]
   - 2026-02-08 Daily Report: "Water Sleeping Mask ranked #6..."
   - 2026-02-01 Daily Report: "Product showed upward trend..."
   - 2026-01-25 Daily Report: "Ranking improved from #12 to #8..."
   ```

4. Response
   > "Water Sleeping Mask는 1월 중순 #12에서 시작해 점진적으로
   > 상승했습니다. 2월 초 #8까지 상승한 후 현재는 #6을 유지 중이며,
   > 이는 주로 긍정적인 보습 관련 리뷰 증가와 연관이 있습니다."

### 시나리오 2: 커스텀 레포트 생성

**User**: "경쟁사 대비 우리 제품 포지셔닝 분석" + 카테고리별 TOP5 데이터

**Process**:
1. Similar Report Search
   - Query: "경쟁사 포지셔닝"
   - Doc Type: CUSTOM
   - Results: 2개 유사 Custom Report

2. Reference Context
   ```
   [SIMILAR_PAST_REPORTS_FOR_REFERENCE]
   - "경쟁사 대비 포지셔닝 분석 (2026-01)"
     → 분석 구조: 카테고리별 / 가격대별 / 리뷰 분석
   - "카테고리 경쟁력 분석 (2025-12)"
     → 분석 구조: 순위 추이 / 점유율 / 강점/약점
   ```

3. Report Generation
   - 과거 레포트 구조 참고
   - 일관된 분석 프레임워크
   - 새로운 데이터 기반 인사이트

### 시나리오 3: 제품 비교 질문

**User**: "Lip Glowy Balm과 Lip Sleeping Mask 중 어느 제품이 최근 성과가 좋나요?"

**Process**:
1. Multi-Product Query
   - Extract: ["Lip Glowy Balm", "Lip Sleeping Mask"]
   - Search for both products

2. RAG Search (각 제품)
   - Recent reports mentioning each product
   - Performance metrics (ranking, reviews, ratings)

3. Comparative Analysis
   > "최근 2주 데이터를 보면 Lip Sleeping Mask가 더 강한 상승세를
   > 보이고 있습니다. (#12 → #6, 4단계 상승)
   > 반면 Lip Glowy Balm은 #8~#10 사이에서 안정적으로 유지 중입니다.
   > 리뷰 수는 Lip Sleeping Mask가 더 많지만,
   > 평점은 두 제품 모두 4.5+ 로 유사합니다."

---

## 성능 최적화

### 1. Caching

**Embeddings Cache**:
```python
# core/embeddings.py
_embeddings_cache = None  # Singleton pattern

def get_embeddings():
    global _embeddings_cache
    if _embeddings_cache is None:
        _embeddings_cache = OpenAIEmbeddings(...)
    return _embeddings_cache
```

### 2. Batch Processing

**Chunk Insertion**:
```python
# Safe mode: 개별 execute (느리지만 안정적)
use_safe_insert=True

# Performance mode: executemany (빠르지만 ORA-01484 위험)
use_safe_insert=False
```

### 3. Index Optimization

**Oracle Vector Index**:
```sql
-- IVF (Inverted File Index)
CREATE VECTOR INDEX idx_rag_chunks_embedding
ON rag_doc_chunks(embedding)
ORGANIZATION NEIGHBOR PARTITIONS
WITH DISTANCE COSINE;
```

### 4. Query Optimization

**Top-K Limiting**:
- Chat: 3개 청크 (빠른 응답)
- Custom Report: 2개 레포트 (일관성)
- Debug: 5-10개 (상세 분석)

**Similarity Threshold**:
- 기본: 0.7 (높은 품질)
- 넓은 검색: 0.5
- 정확한 검색: 0.8+

---

## 향후 개선 방향

### 1. Hybrid Search

**Keyword + Semantic**
- BM25 (keyword) + COSINE (semantic)
- 가중치 조합으로 최적 결과

### 2. Re-ranking

**Two-Stage Retrieval**
1. Fast retrieval (Top-100)
2. Re-ranking with cross-encoder (Top-K)

### 3. Query Expansion

**자동 쿼리 확장**
- 동의어 추가 ("립밤" → "립케어", "립")
- 제품명 변형 ("립 슬리핑 마스크" → "Lip Sleeping Mask")

### 4. Metadata Enrichment

**추가 메타데이터**
```json
{
  "product_ids": [1, 3, 5],
  "keywords": ["ranking", "review", "competitive"],
  "categories": ["Lip Care"],
  "sentiment": "positive"
}
```

### 5. Fine-tuning

**도메인 특화 임베딩**
- 화장품 용어 학습
- 한국어 최적화
- 제품명 인식 향상

### 6. Multi-modal RAG

**이미지 + 텍스트**
- 제품 이미지 검색
- 차트/그래프 인식
- 비주얼 인사이트 결합

---

## 참고 자료

### Papers
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906)

### Technologies
- [LangChain RAG Documentation](https://python.langchain.com/docs/use_cases/question_answering/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [Oracle Vector Search](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/)

---

## 결론

InsightPocket의 RAG 시스템은 **과거 레포트를 활용하여 더 정확하고 일관된 인사이트를 제공**합니다.

**핵심 가치**:
1. 일관성 있는 분석 프레임워크
2. 실제 데이터 기반 답변
3. 트렌드 분석 가능
4. 누적된 지식 활용

**향후 방향**:
- Hybrid search로 검색 품질 향상
- 도메인 특화 fine-tuning
- Multi-modal 지원
