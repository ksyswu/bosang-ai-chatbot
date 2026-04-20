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

# --- [3] 세션 관리 및 사이드바 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 가성비 최고 ✨
- **B 등급**: 생활 기스 있음 💯
- **가성비**: 실속파용 (기스/찍힘 있음) 💪
- **진열상품**: 매장 전시용. 배터리 최상 🚀
    """)

guide_text = """
**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘"
- "**아이폰 15 Pro** S급 재고 있어?"
- "**운동용 애플워치** 추천해줘"
"""

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

if not st.session_state.messages:
    welcome_msg = f"반갑습니다! 보상나라 점장입니다. 😊 어떤 기기를 찾으시나요? 장부에서 상태 좋고 가격 착한 제품으로 딱 골라드릴게요!  \n{guide_text}"
    st.session_state.messages.append({"role": "assistant", "content": welcome_msg, "df": None})
    st.rerun()

# --- [4] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        grade_kw = ["등급", "상태", "기준", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "프로", "에어"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        context_kw = ["편집", "용도", "사용", "적합", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "그림", "드로잉", "가능", "돼", "될까"]

        if any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + context_kw)):
            response = """보상나라의 등급 기준을 안내해 드립니다! 😊

**S 등급**: 신품급 상태 (선물용 추천)  
**A 등급**: 흠집 없이 깔끔함 (인기 최고)  
**B 등급**: 미세 생활 기스 (실속형)  
**가성비**: 기능 정상, 외관 기스 있음  
**진열상품**: 전시 모델, 배터리 상태 최상"""
            st.session_state.is_in_consult = False
            final_df = None

        elif any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + context_kw)):
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                st.session_state.last_category = current_cat
                stock_result = full_cat_df.head(3) 
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [상담 원칙]
                1. 단일 모델 원픽 추천: 추천할 때는 무조건 질문에 가장 적합한 '모델 하나'만 골라서 집중적으로 설명해. 여러 개를 나열하면 손님이 헷갈려해.
                2. 표현 주의: '녀석'이라는 표현은 절대 사용하지 마. 대신 '모델', '제품', '기기'라고 정중하게 지칭해.
                3. 상향판매 & 논리: 추천한 모델보다 더 좋은 성능이 필요한 질문이 들어오면 재고 내 상위 모델을 비교 제안해. 단, 답변은 간결하고 명확하게 유지해.
                4. 데이터 엄수: 재고 데이터({stock_list})에 없는 스펙이나 모델은 절대 지어내지 마.
                5. 가독성: 큰 제목(#) 사용 금지. 굵게(**)와 줄바꿈을 활용하고, 답변이 너무 길어지지 않게 핵심만 말해."""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.0 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            response = f"죄송합니다, 손님! 질문을 정확히 이해하지 못했어요. 아래 예시처럼 말씀해주시면 장부에서 바로 찾아드릴게요!  \n{guide_text}"
            st.session_state.is_in_consult = False
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
