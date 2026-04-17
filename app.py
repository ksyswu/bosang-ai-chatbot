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

# --- [4] 사이드바 (등급 기준 고정) ---
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
        
        # 키워드 체계 정립
        grade_kw = ["등급", "기준", "상태", "등급이뭐야", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "에어", "프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "가격", "있어", "있나요", "춫ㄴ"]
        context_kw = ["편집", "용도", "사용", "적합", "무게", "배터리", "인강", "학교", "가벼운", "성능", "게임", "프로그래밍", "개발", "더"]

        # A. 등급 기준 질문 우선 대응
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        
        # B. 추천 및 재고 질문 대응
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_grade_query:
            response = """보상나라의 등급 기준을 안내해 드릴게요! ✨
            
1. **S 등급**: 신품급 상태로 선물용으로 인기가 가장 많아요. 🎁
2. **A 등급**: 미세한 흔적 정도만 있는 아주 깔끔한 제품이에요. ✨
3. **B 등급**: 생활 기스가 조금 있지만, 가성비가 훌륭하고 기능은 완벽해요. 💯
4. **가성비**: 찍힘이나 흔적이 있지만, 성능 대비 가격이 매우 저렴한 실속파용입니다! 💪
5. **진열상품**: 매장 전시용 모델로, 배터리 효율이 신품급인 경우가 많아요. 🚀

지금 보상나라 장부에 다양한 기종이 준비되어 있는데, 어떤 제품을 먼저 확인해 드릴까요?"""
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
                
                cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
                
                # 대안 제시 여부 확인
                is_alternative = False
                if cat_df.empty:
                    st.session_state.last_category = "아이폰"
                    cat_df = df[df['카테고리'].str.contains("아이폰", na=False)].copy()
                    is_alternative = True
                else:
                    st.session_state.last_category = current_cat

                # 정렬 로직 (더 저렴한 것 찾을 때 가격순 정렬)
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    stock_result = cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [점장님 최종 훈육 지침]
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [영업 및 정직 원칙]
                1. 100% 팩트 가격: [오늘의 실제 재고]에 있는 '판매가_표기'를 텍스트로 당당히 언급해. 절대 지어내지 마.
                2. 질문 리스트 제안: 답변 마지막에 반드시 손님이 클릭하거나 물어보기 좋은 예시 질문 2~3개를 "**💡 이렇게 물어보세요!**" 섹션으로 넣어줘.
                3. 로봇 멘트 금지: "다음 질문을 고려해보세요" 같은 딱딱한 말투 금지. "점장인 제가 추천드리는 다음 단계는요~"처럼 자연스럽게 제안해.
                4. 대안 추천: {current_cat} 재고가 없으면(is_alternative=True), 운동/휴대 등 용도에 맞춰 아이폰을 노련하게 추천해.
                5. 허구 지연 차단: 무게, 사진 촬영, 입고일정 등 네가 알 수 없는 정보는 절대 확답하지 마.

                [오늘의 실제 재고 데이터]:
                {stock_list}
                [대안 추천 여부]: {is_alternative}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.0 # 환각 방지용 온도
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            # 기본 대기 상태 (질문 가이드 포함)
            response = """반갑습니다! 보상나라 점장입니다. 😊  
어떤 기기를 찾으시나요? 장부에서 가장 상태 좋고 가성비 넘치는 녀석으로 골라드릴게요!

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
