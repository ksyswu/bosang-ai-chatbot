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
st.markdown('<p class="sub-title">장부 확인 완료! 점장님이 직접 선별한 최적의 기기만 정직하게 추천합니다. ✨</p>', unsafe_allow_html=True)

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

# --- [4] 사이드바 (등급 기준) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨
- **B 등급**: 생활 기스 있음. 기능은 완벽 💯
- **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪
- **진열상품**: 매장 전시용. 배터리 효율 최상 🚀
    """)

# 이전 대화 출력
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
        laptop_kw = ["맥북", "노트북", "컴퓨터", "에어", "프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요", "춫ㄴ"]
        context_kw = ["편집", "용도", "사용", "적합", "무게", "배터리", "인강", "학교", "사진", "카메라", "성능", "게임", "수영", "운동", "방수"]

        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                # 카테고리 결정
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                else: current_cat = st.session_state.last_category
                
                cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
                
                # 재고가 없는 경우 '아이폰'으로 대안 유도
                is_alternative = False
                if cat_df.empty:
                    st.session_state.last_category = "아이폰"
                    cat_df = df[df['카테고리'].str.contains("아이폰", na=False)].copy()
                    is_alternative = True
                else:
                    st.session_state.last_category = current_cat

                # 모델 선정
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    stock_result = cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                [미션] 장부에 있는 제품을 장점 어필하여 판매로 연결하라.
                
                [수칙]
                1. 대안 추천: {current_cat} 재고가 없으면(is_alternative=True), 실망시키지 말고 현재 장부에 있는 아이폰을 대안으로 노련하게 추천해.
                2. 거짓 금지: 무게(kg), 사진 약속, 재입고 날짜 지어내지 마.
                3. 화법: 앵무새처럼 질문 반복 금지. 친절한 줄바꿈과 이모지 사용.
                4. 가이드 제공: 답변 끝에 항상 고객이 궁금해할 만한 '다음 질문' 3가지를 리스트로 제안해.

                [오늘의 실제 재고]: {stock_list}
                [대안 추천 여부]: {is_alternative}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.2
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
                st.markdown(response)
                with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                    st.table(final_df)
                st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        
        else:
            # 못 알아들었거나 초기 화면일 때 질문 리스트 제안
            response = """반갑습니다! 보상나라 점장입니다. 😊  
지금 바로 구매 가능한 최고의 기기들을 장부에서 찾아드릴게요. 어떤 제품이 필요하신가요?

**💡 점장님에게 이렇게 물어보시면 빨라요!**
- "학교에서 쓸 **가벼운 맥북** 추천해줘" 💻
- "**아이폰 15 Pro** S급 재고 있어?" 📸
- "영상 편집용 **성능 좋은 노트북** 찾아줘" 🎬"""
            st.markdown(response)
            st.session_state.is_in_consult = False
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
