import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #1E1E1E; }
    .sub-title { font-size: 15px; color: #666; margin-bottom: 20px; }
    .stTable { width: 100%; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">장부 데이터에 기반해 정직하게 안내합니다. 과장 없이 핵심 재고만 보여드릴게요.</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 (기존 로직 유지) ---
@st.cache_data
def load_inventory():
    file_name = "inventory.xlsx" 
    try:
        df = pd.read_excel(file_name, sheet_name='Sheet1')
        df.columns = [str(c).strip() for c in df.columns]
        df['판매가'] = pd.to_numeric(df['판매가'], errors='coerce').fillna(0)
        df['판매가_표기'] = df['판매가'].apply(lambda x: "{:,}원".format(int(x)))
        if '배터리' in df.columns:
            df['배터리_표기'] = pd.to_numeric(df['배터리'], errors='coerce').apply(
                lambda x: f"{int(x * 100)}%" if pd.notnull(x) and x <= 1 else (f"{int(x)}%" if pd.notnull(x) else "정보없음")
            )
        return df
    except: return None

df = load_inventory()

# --- [3] 세션 관리 (맥락 유지) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

# --- [4] 사이드바 (등급 기준 고정) ---
with st.sidebar:
    st.header("✨ 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추 🎁
    - **A 등급**: 깔끔함. 가성비 최고 ✨
    - **B 등급**: 생활 기스 있음. 기능 완벽 💯
    - **가성비/진열**: 외관 흔적 있으나 저렴 💪
    """)

# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 체계 (기존 누락 방지)
        grade_kw = ["등급", "기준", "상태"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑", "맥북에어", "맥북프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요", "찾아"]
        context_kw = ["편집", "용도", "사용", "적합", "응", "더", "무게", "배터리", "인강", "학교", "사진", "카메라", "촬영"]

        # 의도 분류 로직
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        response = ""
        final_df = None

        # CASE 1: 등급 문의
        if is_grade_query:
            response = "보상나라 등급은 S(신품급), A(우수), B(실속), 가성비(진열상품)로 운영됩니다. 구체적으로 찾는 기종이 있으신가요?"
            st.session_state.is_in_consult = False

        # CASE 2: 제품 추천 및 상담 (보완 핵심)
        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                # 카테고리 업데이트
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 가격순 정렬/필터링
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    search_word = user_input.split()[0] if len(user_input.split()) > 0 else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [강화된 전문가 프롬프트: 아이콘 제거 및 담백한 어조]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야.
                [상담 원칙]
                1. 아이콘 사용 최소화: 문장 끝마다 아이콘(📸, 🎁)을 붙이지 마. 꼭 필요한 곳에만 한두 개 써서 전문성을 유지해.
                2. 가격 조작 금지: 텍스트로 가격을 직접 지어내지 마. 가격 정보는 하단 [상세 사양 표]를 참고하라고 하거나, 데이터에 있는 판매가 표기만 정확히 읽어줘.
                3. 간결한 구어체: "점장님이 추천하는~", "할 수 있어요" 같은 불필요한 수식어를 빼고 "사양 충분합니다", "이게 가성비가 제일 좋네요" 처럼 짧고 단호하게 말해.
                4. 재고 부재 시 대안 제시: 고객이 찾는 특정 모델이 장부에 없으면 "그 제품은 현재 없지만, 대안으로 이런 모델이 좋습니다"라며 [실재고]를 추천해.
                5. 맥락 유지: {st.session_state.last_category}를 주제로 대화를 이어가.
                
                [오늘의 실제 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)

        # CASE 3: 기본 안내 (질문 리스트 포함)
        else:
            response = """어떤 제품을 찾으시나요? 모델명이나 용도를 말씀해 주시면 장부를 확인해 드릴게요. 😊
            
- "인강용 **저렴한 맥북** 있어?"
- "**아이폰 15 Pro** 재고 확인해줘"
- "보상나라 **등급 기준**이 뭐야?" """
            st.session_state.is_in_consult = False

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
