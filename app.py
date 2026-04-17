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
st.markdown('<p class="sub-title">장부 확인 완료! 점장님이 직접 선별한 기기만 정직하게 추천합니다. ✨</p>', unsafe_allow_html=True)

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
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

# --- [4] 사이드바 ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 🎁  
- **A 등급**: 깔끔함 ✨  
- **B 등급**: 생활 기스 💯  
- **가성비**: 실속파 💪  
- **진열상품**: 배터리 최상 🚀
    """)

# 대화 로그 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 체계
        grade_kw = ["등급", "기준", "상태", "등급기준", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "에어", "프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요"]
        context_kw = ["편집", "용도", "사용", "적합", "무게", "배터리", "인강", "학교", "성능", "게임", "프로그래밍"]

        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_grade_query:
            response = "보상나라의 등급 기준은 S(신품급), A(깔끔함), B(생활기스), 가성비, 진열상품으로 나뉩니다. 😊"
            final_df = None
        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                # 카테고리 결정
                if any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
                
                # '더 저렴한' 요청 대응
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    stock_result = cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [점장님 정밀 타격 지침]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [가장 중요한 데이터 매칭 수칙]
                1. 100% 팩트만 언급: 아래 제공된 [오늘의 실제 재고] 리스트에 있는 '상품명', '판매가_표기', '등급', '배터리_표기' 정보만 사용해.
                2. 가격 언급 필수: "이 모델은 00원입니다"라고 명확히 말해줘. 단, 숫자는 반드시 장부와 일치해야 해.
                3. 지어내기 금지: 장부에 없는 사양(예: 16G 램, 1TB 용량 등)이나 가격은 절대 말하지 마. 장부에 없으면 "현재 그 사양은 없지만, 이 모델이 대안으로 좋다"고 말해.
                4. 영업 화법: "인강용으로 딱이다", "상태가 아주 좋다"는 식으로 장점을 강조해서 구매를 유도해.
                5. 로봇 말투 금지: "다음 질문을 고려해보세요" 금지. 자연스러운 대화로 끝내.

                [오늘의 실제 재고 데이터]:
                {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.0 # 환각 방지를 위해 0으로 고정
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
        else:
            response = "반갑습니다! 보상나라 점장입니다. 무엇을 도와드릴까요? 😊"
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
