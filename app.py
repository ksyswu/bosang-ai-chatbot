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
- **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨
- **B 등급**: 생활 기스 있음. 기능은 완벽 💯
- **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪
- **진열상품**: 매장 전시용. 배터리 효율 최상 🚀
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
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요", "춫ㄴ"]
        context_kw = ["편집", "용도", "사용", "적합", "배터리", "인강", "학교", "성능", "게임", "더"]

        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_grade_query:
            response = """보상나라의 등급 기준을 안내해 드릴게요! ✨
            
1. **S 등급**: 신품급 상태로 선물용으로 인기가 가장 많아요. 🎁
2. **A 등급**: 미세한 흔적 정도만 있는 아주 깔끔한 제품이에요. ✨
3. **B 등급**: 생활 기스가 조금 있지만 가성비가 훌륭해요. 💯
4. **가성비/진열**: 실속파를 위한 저렴한 모델들입니다. 🚀

관심 있는 기종의 재고를 확인해 드릴까요?"""
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
                
                cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
                
                if cat_df.empty:
                    st.session_state.last_category = "아이폰"
                    cat_df = df[df['카테고리'].str.contains("아이폰", na=False)].copy()
                    is_alternative = True
                else:
                    st.session_state.last_category = current_cat
                    is_alternative = False

                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    stock_result = cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [상담 원칙]
                1. 추천 시 가이드 생략: 이미 제품을 추천하고 가격을 말할 때는 "질문 리스트"나 "💡 이렇게 물어보세요" 같은 문구를 절대 쓰지 마. 흐름이 깨져.
                2. 구매 확신 유도: 대신 "상태가 좋아 금방 나갈 것 같습니다"나 "이 정도면 정말 가성비 최고죠" 같은 멘트로 대화를 마무리해.
                3. 데이터 엄수: [오늘의 실제 재고]에 있는 가격({stock_list})만 말해.
                4. 대안 추천: 재고가 없으면(is_alternative=True) 정직하게 말하고 아이폰을 대안으로 제안해.

                [오늘의 실제 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.0
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            # 질문을 못 알아들었거나 처음 시작할 때만 '질문 가이드' 노출
            response = """반갑습니다! 보상나라 점장입니다. 😊  
어떤 기기를 찾으시나요? 장부에서 가장 상태 좋은 녀석으로 골라드릴게요!

**💡 점장님에게 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘" 💻
- "**아이폰 15 Pro** S급 재고 있어?" 📸
- "보상나라 **등급 기준** 알려줘" 📋"""
            st.session_state.is_in_consult = False
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
