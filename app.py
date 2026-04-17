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

# --- 3. 대화 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

# 사이드바 (등급표 상시 노출)
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("- **S 등급**: 신품급! 🎁  \n- **A 등급**: 미세 흔적, 가성비 ✨  \n- **B 등급**: 생활 기스 있음 💯")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 4. 상담 엔진 (대화 유도 로직 추가) ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # 키워드 사전 (카테고리 판별용)
        watch_kw = ["워치", "시계", "수영", "운동", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰"]
        mac_kw = ["맥북", "노트북", "코딩", "작업", "편집"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마"]

        # 카테고리 업데이트
        if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
        elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
        elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
        elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"

        is_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw)) or "등급" in q_clean
        
        response = ""
        final_df = None

        if is_talk and len(q_clean) >= 2:
            with st.spinner("장부를 확인 중입니다..."):
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 1. 사용자가 말한 특정 모델 검색 (예: "아이폰 16")
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(user_input.split()[0], case=False, na=False)]
                
                # 2. 검색 결과가 없으면 해당 카테고리 전체 재고를 보여주지 말고 "최상위 2~3개"만 대안으로 준비
                if target_stock.empty:
                    stock_result = cat_df.head(2) # 리스트 최소화
                    resp_situation = "alternative" # 대안 추천 상황
                else:
                    stock_result = target_stock.head(3) # 검색된 것 중 3개만
                    resp_situation = "recommend"

                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라' 점장이야. 
                [필독 규칙]
                1. 한자를 절대 사용하지 마.
                2. [상황]이 'alternative'라면 "찾으시는 모델은 현재 매장 장부에 없지만, 비슷한 급의 다른 모델을 보여드릴게요"라고 정중히 안내해.
                3. **[중요]** 답변 마지막에 "고객님, 주로 어떤 용도(유튜브, 게임, 촬영 등)로 사용하실 예정인가요? 말씀해 주시면 딱 맞는 모델을 더 정밀하게 추천해 드릴 수 있습니다!"라고 반드시 질문해.
                4. [재고] 리스트에 있는 모델만 간단히 언급해. 리스트가 너무 길면 핵심만 말해.
                
                [상황]: {resp_situation}
                [재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.4
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]

        # 답변 불가 시 가이드 (이전과 동일)
        if not response:
            response = "어이쿠 고객님! 제가 그 부분은 답변이 어려워요 😅  \n\n**💡 이렇게 물어보세요!** \n1. '촬영용 아이폰 추천해줘' 📸  \n2. '보상나라 등급 기준이 뭐야?' 📋"

        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
