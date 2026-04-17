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

# --- [3] 세션 관리 (문맥 유지의 핵심) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

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
        
        # 키워드 체계 (용도 및 문맥 인지 강화)
        laptop_kw = ["맥북", "노트북", "컴퓨터", "프로", "에어"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        context_kw = ["편집", "용도", "사용", "적합", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "그림", "드로잉", "가능", "돼", "될까", "있어"]

        # 추천 대화 여부 판단 (카테고리 명시 혹은 상담 중 용도 질문)
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        if is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                # 카테고리 결정
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                st.session_state.last_category = current_cat
                
                # 최저가 및 추천 데이터 (상위 2개 추출하여 AI가 비교/선택하게 함)
                abs_lowest_price = full_cat_df['판매가_표기'].iloc[0] if not full_cat_df.empty else ""
                stock_result = full_cat_df.head(2)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                가장 큰 원칙: 장부 데이터를 기반으로 '정직'하게 추천하고, '단일 모델'을 주인공으로 세워 설득해.

                [상담 및 가독성 지침]
                1. 원픽 추천: 여러 모델 나열 대신, 질문에 가장 적합한 모델 하나를 딱 찍어서 추천해.
                2. 추론 기반 추천 이유: 단순히 '베스트'라고 하지 마. 장부의 사양과 추천포인트를 조합해서 "이 모델은 램이 넉넉해서 프로그래밍에 끊김이 없다"는 식으로 전문가적 근거를 들어줘.
                3. 대화 문맥 유지: "그것도 돼?" 같은 질문에 "그럼요! 아까 본 그 모델이면 충분합니다"라고 이어가. 처음 인사(가이드)를 반복하지 마.
                4. 시스템 용어 박멸: '카테고리', '상세모델', '상품명(정제형)' 같은 말은 절대 쓰지 마.
                5. 가독성 최적화: 큰 제목(#)은 글자가 너무 커지니 절대 쓰지 마. 항목별로 줄바꿈을 철저히 지켜.
                6. 거짓 금지: 사양이 부족하면 정직하게 말하고 상위 모델을 권해. (예: "인강용으론 좋지만 전문 편집은 무리입니다")
                7. 답변 끝에 '💡 가이드'는 절대 넣지 마.

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
            # 초기 화면 혹은 알 수 없는 질문 시에만 가이드 노출
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
