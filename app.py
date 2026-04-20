import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #1E1E1E; }
    .stTable { width: 100%; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 ---
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

# --- [3] 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

# 사이드바 등급 안내
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("- **S 등급**: 신품급\n- **A 등급**: 깔끔함\n- **B 등급**: 실속형\n- **가성비**: 외관기스\n- **진열상품**: 배터리 최상")

guide_text = """
**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘"
- "**아이폰 15 Pro** S급 재고 있어?"
"""

# 대화 로그 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

if not st.session_state.messages:
    welcome = f"반갑습니다! 보상나라 점장입니다. 😊 어떤 기기를 찾으시나요?  \n{guide_text}"
    st.session_state.messages.append({"role": "assistant", "content": welcome, "df": None})
    st.rerun()

# --- [4] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q = user_input.replace(" ", "").lower()
        
        # 키워드 분류
        is_laptop = any(kw in q for kw in ["맥북", "노트북", "컴퓨터", "에어", "프로"])
        is_phone = any(kw in q for kw in ["폰", "아이폰", "갤럭시"])
        is_pad = any(kw in q for kw in ["패드", "아이패드", "태블릿"])
        is_context = any(kw in q for kw in ["편집", "용도", "사용", "인강", "추천", "저렴", "싼", "가격", "얼마", "프로그래밍", "가능", "돼"])

        if is_laptop or is_phone or is_pad or is_context:
            with st.spinner("장부 확인 중..."):
                # 카테고리 유지 및 결정
                if is_laptop: cat = "맥북"
                elif is_phone: cat = "아이폰"
                elif is_pad: cat = "아이패드"
                else: cat = st.session_state.last_category
                st.session_state.last_category = cat

                # [핵심] 질문 의도에 따른 데이터 '맞춤 정렬'
                f_df = df[df['카테고리'].str.contains(cat, na=False)]
                
                if any(kw in q for kw in ["저렴", "싼", "가격", "얼마"]):
                    f_df = f_df.sort_values(by='판매가', ascending=True) # 저렴한 순
                elif any(kw in q for kw in ["편집", "프로그래밍", "고사양", "성능"]):
                    f_df = f_df.sort_values(by='판매가', ascending=False) # 고성능 순
                else:
                    f_df = f_df.sort_values(by='판매가', ascending=False) # 기본은 베스트 매물

                stock_result = f_df.head(3)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                중요: '지침', '리스트' 같은 단어는 절대 노출하지 마. 오직 점장의 말투로만 답해.

                [영업 지침]
                1. 추천 일치: 재고({stock_list}) 중 '첫 번째' 모델을 반드시 메인 주인공(📍 모델명)으로 추천해.
                2. 문맥 유지: 이전 대화를 기억해서 "방금 말씀드린 모델은~" 처럼 자연스럽게 이어가.
                3. 양식: 📍모델명, ✨등급, 💰판매가, 🔋배터리 상태, 💬점장 큐레이션 순서 엄수.

                보상나라는 전문가가 검수를 마친 안전한 제품만 판매합니다."""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             st.session_state.messages[-5:], # 대화 맥락 유지 위해 이전 메시지 전달
                    temperature=0.0 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            response = f"질문을 이해하지 못했어요. 모델명이나 용도를 말씀해 주시겠어요?  \n{guide_text}"
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
