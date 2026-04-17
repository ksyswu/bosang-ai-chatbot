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

# --- [3] 세션 관리 (문맥 유지 및 사이드바 복구) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

# [사이드바 등급 안내 - 복구 완료]
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
        
        laptop_kw = ["맥북", "노트북", "컴퓨터", "프로", "에어"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        context_kw = ["편집", "용도", "사용", "적합", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "그림", "드로잉", "가능", "돼", "될까", "있어"]

        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                st.session_state.last_category = current_cat
                
                abs_lowest_price = full_cat_df['판매가_표기'].iloc[0] if not full_cat_df.empty else ""
                # 비교군까지 포함하여 AI에게 전달 (상위 2개)
                stock_result = full_cat_df.head(2)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                가장 큰 원칙: 장부 데이터를 기반으로 정직하게 '장사'를 해. 

                [상담 지침: 상향 판매와 정직함]
                1. 성능 맞춤 추천: 손님이 특정 용도(편집, 개발 등)를 물었을 때, 현재 추천 모델이 부족하다면 재고 리스트에서 더 높은 사양의 모델을 당당하게 제안해. (예: "전문 편집까지 하시려면 아까 그 모델보다 이 16인치 모델이 램이 두 배라 훨씬 쾌적합니다!")
                2. 원픽 지향: 가장 적절한 '베스트' 제품을 주인공으로 하되, 사양 차이를 논리적으로 설명해.
                3. 데이터 용어 제거: '카테고리', '상세모델', '상품명(정제형)' 같은 말은 절대 쓰지 마.
                4. 가독성: 큰 제목(#)은 금지. 일반 텍스트와 굵게(**)만 사용하고 줄바꿈을 철저히 해.
                5. 문맥 유지: "그건 돼?" 질문에 "그럼요, 아까 본 그 제품은 가능하죠" 혹은 "그건 조금 버거우니 이 모델이 낫습니다"라고 자연스럽게 이어가.
                6. 답변 끝에 가이드(💡)는 넣지 마.

                [오늘의 실제 재고 데이터]: {stock_list}
                [매장 내 최저가 정보]: {abs_lowest_price}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.0 
                ).choices[0].message.content
                
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
