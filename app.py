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

# --- [3] 세션 및 사이드바 (대전제: 누락 금지) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

# [사이드바 상시 노출]
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 가성비 최고 ✨
- **B 등급**: 생활 기스 있음 💯
- **가성비**: 실속파용 (기스/찍힘 있음) 💪
- **진열상품**: 매장 전시용. 배터리 최상 🚀
    """)

# 채팅 로그 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

# --- [4] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 체계
        grade_kw = ["등급", "상태", "기준", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "프로", "에어"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        context_kw = ["편집", "용도", "사용", "적합", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "그림", "드로잉", "가능", "돼", "될까"]

        # 1. 등급 기준 질문인 경우
        if any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + context_kw)):
            response = """보상나라의 정직한 등급 기준을 안내해 드립니다! 😊

**S 등급**: 새 제품과 다름없는 최상급 상태 (선물용 추천)
**A 등급**: 눈에 띄는 흠집 없이 깔끔한 상태 (인기 최고)
**B 등급**: 미세한 생활 기스가 있는 실속형 상태
**가성비**: 외관 기스는 있으나 기능은 완벽 (가격 중시)
**진열상품**: 매장에 전시되었던 배터리 상태 최상급 모델

찾으시는 모델을 말씀해 주시면 이 기준에 맞춰 딱 골라드릴게요!"""
            st.session_state.is_in_consult = False
            final_df = None

        # 2. 추천 상담인 경우
        elif any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw)) or \
             (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw)):
            
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                st.session_state.last_category = current_cat
                
                # 상위 2개 재고 추출
                stock_result = full_cat_df.head(2)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라 베테랑 점장이야. 
                [핵심 가이드]
                1. 원픽 추천: 용도에 맞는 '최적의 모델 하나'를 주인공으로 세워 추천해.
                2. 상향 판매: 손님의 용도에 비해 사양이 부족하면, 재고 리스트에서 더 높은 사양을 이유와 함께 제안해.
                3. 추론 기반 설명: 장부의 추천포인트를 넘어, "왜" 이 작업에 좋은지 전문가처럼 설명해.
                4. 용어 제거: '카테고리', '상세모델', '상품명(정제형)' 절대 쓰지 마.
                5. 가독성: 큰 제목(#) 금지. 굵게(**)와 줄바꿈만 사용해.
                6. 답변 끝에 가이드(💡)는 넣지 마.

                [오늘의 실제 재고 데이터]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.0 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        # 3. 그 외 (초기 가이드)
        else:
            response = """반갑습니다! 보상나라 점장입니다. 😊 어떤 기기를 찾으시나요?  
장부에서 가장 상태 좋고 가격 착한 녀석들로 딱 골라드릴게요!

**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘"
- "**아이폰 15 Pro** S급 재고 있어?" """
            st.session_state.is_in_consult = False
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
