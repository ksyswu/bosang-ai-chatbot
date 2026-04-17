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

# --- [4] 사이드바 (등급 기준) ---
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
            response = "보상나라의 등급 기준은 S(신품급), A(깔끔함), B(생활기스), 가성비, 진열상품으로 나뉩니다. 자세한 내용은 왼쪽 사이드바를 확인해 주세요! 😊"
            st.session_state.is_in_consult = False
            final_df = None

        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                # 카테고리 판별
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                # 재고 필터링 및 최저가 파악
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                is_alternative = False
                abs_lowest_price = ""

                if full_cat_df.empty:
                    st.session_state.last_category = "아이폰"
                    full_cat_df = df[df['카테고리'].str.contains("아이폰", na=False)].sort_values(by='판매가')
                    is_alternative = True
                
                st.session_state.last_category = current_cat
                abs_lowest_price = full_cat_df['판매가_표기'].iloc[0] if not full_cat_df.empty else ""
                stock_result = full_cat_df.head(2)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [점장님 최종 훈육 지침]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 손님의 질문 의도를 정확히 파악해서 장사꾼답게 대답해.

                [절대 준수 지침]
                1. 최저가 논리: 손님이 '더 싼 것'을 찾을 때, 현재 추천 모델 가격이 매장 최저가({abs_lowest_price})와 같다면 "지금 보시는 제품이 저희 매장 전체에서 가장 저렴한 최저가 모델입니다"라고 확신을 줘. 
                2. 용도별 차별화: 프로그래밍, 영상편집, 학교 등 용도에 맞춰 '램 용량', '휴대성', '가성비' 등 세일즈 포인트를 다르게 짚어줘. 앵무새처럼 같은 말 반복 금지.
                3. 시스템 용어 노출 금지: '카테고리:', '상세모델:', '상품명(정제형):' 같은 단어는 답변 텍스트에 절대 쓰지 마. 자연스러운 문장으로만 말해.
                4. 추천 시 가이드 생략: 제품 추천이 나갈 때는 "💡 이렇게 물어보세요" 가이드를 절대 출력하지 마.
                5. 정직한 영업: 장부에 없는 정보(램 업그레이드 여부, 입고 예정일, 실시간 사진 전송 등)를 지어내지 마.

                [오늘의 실제 재고 데이터]: {stock_list}
                [매장 내 최저가 정보]: {abs_lowest_price}
                [대안 추천 상태]: {is_alternative}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.2 # 약간의 유연성을 주어 앵무새 답변 방지
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            # 초기 상태 또는 이해 불능 시에만 가이드 노출
            response = """반갑습니다! 보상나라 점장입니다. 😊  
어떤 기기를 찾으시나요? 장부에서 가장 상태 좋고 저렴한 녀석으로 골라드릴게요!

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
