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
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 가성비 최고 ✨
- **B 등급**: 생활 기스 있음 💯
- **가성비**: 실속파용 (기스/찍힘 있음) 💪
- **진열상품**: 매장 전시용. 배터리 최상 🚀
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
        grade_kw = ["등급", "기준", "상태", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "에어", "프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요"]
        context_kw = ["편집", "용도", "사용", "적합", "배터리", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "더"]

        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_grade_query:
            response = "보상나라 등급은 S(신품급), A(깔끔함), B(생활기스), 가성비, 진열상품으로 나뉩니다. 자세한 건 왼쪽 사이드바를 확인해 주세요! 😊"
            st.session_state.is_in_consult = False
            final_df = None

        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                is_alternative = False

                if full_cat_df.empty:
                    st.session_state.last_category = "아이폰"
                    full_cat_df = df[df['카테고리'].str.contains("아이폰", na=False)].sort_values(by='판매가')
                    is_alternative = True
                
                st.session_state.last_category = current_cat
                abs_lowest_price = full_cat_df['판매가_표기'].iloc[0] if not full_cat_df.empty else ""
                stock_result = full_cat_df.head(2)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [점장님 최종 지침: 가독성 및 정직한 영업]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                불필요한 미사여구는 빼고, 핵심 정보 위주로 '줄바꿈'을 잘 지켜서 깔끔하게 답해.

                [영업 원칙]
                1. 구조화된 답변: 모델명, 가격, 추천 포인트를 한 줄씩 구분해서 써.
                2. 가격 쐐기: 현재 추천 모델이 매장 내 최저가({abs_lowest_price})라면 "저희 매장에서 가장 저렴한 최저가 재고입니다"라고 확실히 고지해.
                3. 정직한 리스크 관리: 고사양 작업(편집, 코딩 등) 질문 시 "충분히 가능합니다"라고 확신을 주되, "다만 중고 특성상 무거운 작업 시 발열이나 팬 소음은 감안하셔야 한다"고 정직하게 덧붙여.
                4. 대화의 연속성: 이전 질문에서 된다고 한 것은 "당연히 그것도 가능하죠"라며 시원하게 받아쳐. 했던 말을 로봇처럼 반복하지 마.
                5. 데이터 금지어: '카테고리:', '상세모델:' 등 시스템 필드명 절대 노출 금지. 추천 시 '💡 가이드' 절대 금지.

                [오늘의 실제 재고 데이터]: {stock_list}
                [매장 내 최저가]: {abs_lowest_price}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.0 
                ).choices[0].message.content
                
                # 가독성을 위한 강제 줄바꿈 처리
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
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
