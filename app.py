import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 데이터 로드 ---
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

# --- 3. 사이드바 (등급표 상시 노출) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# --- 4. 대화 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 5. 상담 엔진 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # 키워드 사전
        watch_kw = ["워치", "시계", "수영", "운동", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰", "셀카", "카메라"]
        mac_kw = ["맥북", "노트북", "랩탑", "코딩", "작업", "편집"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "저렴", "싼", "보여줘"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]

        # 카테고리 업데이트
        if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
        elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
        elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
        elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"

        is_trade_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_grade_query = any(kw in q_clean for kw in grade_kw)
        
        response = ""
        final_df = None

        if (is_trade_talk or is_grade_query) and len(q_clean) >= 2:
            with st.spinner("장부를 확인 중입니다..."):
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # [중요] 실제 재고 검색 수행
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(user_input.split()[0], case=False, na=False)]
                
                # 만약 검색 결과가 없으면 해당 카테고리 상위 3개 추천
                if target_stock.empty:
                    stock_result = cat_df.head(3)
                    resp_situation = "alternative" # 재고 없음(대안 추천)
                else:
                    stock_result = target_stock.head(3)
                    resp_situation = "recommend" # 재고 있음

                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [프롬프트 수정] 환각 방지 및 말투 교정
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [필독 규칙]
                1. 한자(예: 需求)를 절대 쓰지 마. 100% 한국어와 적절한 이모지만 사용해.
                2. 특정 모델이 '출시되지 않았다'고 단정 짓지 마. 대신 "현재 저희 매장 장부(재고)에는 해당 모델이 확인되지 않습니다"라고 겸손하게 말해.
                3. [재고] 리스트에 있는 모델만 추천해.
                4. 답변 끝에 반드시 줄바꿈 공백 2개를 넣어.

                [상황] {resp_situation} (검색한 모델이 없으면 대안을 정중히 추천할 것)
                [재고 정보] {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]

        # 답변 불가 시 가이드
        if not response:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  \n전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!  \n\n---\n**💡 이렇게 물어보시면 점장님이 잘 대답해드려요!** \n1. "사진 잘 나오는 **아이폰** 추천해줘" 📸  \n2. "인강/과제용 가성비 **맥북** 있어?" 💻  \n3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚  \n4. "보상나라 **등급 기준**이 궁금해!" 📋  \n---"""

        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
