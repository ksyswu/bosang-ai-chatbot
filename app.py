import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 데이터 로드 함수 ---
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
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return None

df = load_inventory()

# --- 3. 세션 상태 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 등급 가이드 ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비/진열**: 실속파를 위한 합리적 선택 💪  
    """)

# --- 5. 이전 대화 렌더링 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 6. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [키워드 분류]
        watch_kw = ["워치", "시계", "수영", "운동", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰"]
        mac_kw = ["맥북", "노트북", "랩탑"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "사고", "구매", "저렴", "싼"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]
        
        # [용도 파악 플래그]
        purpose_kw = ["용도", "유튜브", "게임", "작업", "인강", "일상", "촬영", "세컨", "서브", "운동"]
        user_already_stated_purpose = any(kw in user_input for kw in purpose_kw)

        is_grade_only = any(kw in q_clean for kw in grade_kw) and not any(kw in user_input for kw in trade_kw)
        is_recommend_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_reply = st.session_state.waiting_for_purpose and len(q_clean) >= 2

        response = ""
        final_df = None

        if is_grade_only:
            response = "보상나라는 S(신품급), A(미세흔적), B(생활기스) 등급을 엄격히 구분합니다! 😊"
            st.session_state.waiting_for_purpose = False

        elif is_recommend_talk or is_reply or len(q_clean) >= 2:
            with st.spinner("장부를 확인 중입니다..."):
                if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
                elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
                elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # [실제 재고 검색]
                search_term = user_input.split()[0]
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_term, case=False, na=False)]
                
                has_actual_stock = not target_stock.empty
                stock_result = target_stock.head(3) if has_actual_stock else cat_df.head(3)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 중고 가전 매장 '보상나라'의 점장이야. 
                [가장 중요한 규칙]
                1. 특정 모델이 '출시되지 않았다'는 거짓말을 절대 하지 마. 
                2. 검색한 모델이 재고에 없으면(has_actual_stock={has_actual_stock}), "현재 저희 매장 장부에는 해당 모델이 확인되지 않습니다"라고만 사실대로 말해.
                3. 재고가 없을 때는 [재고 정보]에 있는 다른 모델을 '대체 추천 상품'으로 정중히 제안해.
                4. 이전 대화에서 언급된 '세컨폰' 같은 용도가 현재 질문과 상관없다면 언급하지 마.
                5. 한자 금지, 줄바꿈 공백 2개 준수.
                
                [재고 정보]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.2 # 사실성을 위해 온도를 낮춤
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]
                
                if not user_already_stated_purpose and not is_reply:
                    response += "  \n\n**고객님, 어떤 용도로 사용하실 예정인가요? 말씀해 주시면 더 정밀하게 추천해 드릴 수 있습니다!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        if not response:
            response = "어이쿠, 고객님! 제가 그 부분은 답변 드리기 어렵네요 😅 '아이폰 추천해줘'처럼 물어봐 주시겠어요?"

        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
