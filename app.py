import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 (이 부분은 반드시 코드 최상단에!) ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 데이터 로드 및 전처리 ---
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

# --- 3. 검색 로직 (카테고리 매칭 고도화) ---
def get_relevant_stock(query, last_cat):
    if df is None: return pd.DataFrame(), "none", last_cat
    
    current_cat = last_cat
    if any(kw in query for kw in ["워치", "시계", "수영", "운동"]): current_cat = "애플워치"
    elif any(kw in query for kw in ["폰", "아이폰"]): current_cat = "아이폰"
    elif any(kw in query for kw in ["맥북", "노트북", "코딩", "프로그래밍"]): current_cat = "맥북"
    elif any(kw in query for kw in ["패드", "아이패드"]): current_cat = "아이패드"

    cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
    q_words = query.split()
    filtered_df = cat_df.copy()
    matched = False
    
    for word in q_words:
        if len(word) > 1 and word not in ["추천", "있어", "보여줘", "가장", "저렴한"]:
            mask = filtered_df['상품명 (정제형)'].str.contains(word, case=False, na=False)
            if mask.any():
                filtered_df = filtered_df[mask]
                matched = True
    
    if filtered_df.empty or not matched:
        return cat_df.sort_values(by='판매가', ascending=False).head(3), "alternative", current_cat
    return filtered_df.head(3), "recommend", current_cat

# --- 4. 사이드바 안내 (항상 표시되도록 보장) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)
    st.divider()
    st.info("💡 '아이폰 13 A급 추천해줘'라고 물어보세요!")

# --- 5. 대화 내역 관리 ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 6. 상담 엔진 (예외 처리 강화) ---
if user_input := st.chat_input("수영용 워치 추천해줘!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [1] 너무 짧거나 의미 없는 입력 (예: 'ㄹ', 'ㅇㅇ') 처리
        is_meaningless = len(q_clean) < 2
        
        # [2] 상담 관련 키워드가 아예 없는 경우
        trade_keywords = ["추천", "가성비", "시세", "얼마", "가격", "사양", "카메라", "게임", "배터리", "운동", "수영", "작업", "저렴", "싼", "있어", "매물", "재고", "코딩", "인강"]
        is_trade_talk = any(kw in user_input for kw in trade_keywords) or any(kw in q_clean for kw in ["S급", "A급", "B급"])

        final_stock_df = None
        
        if is_meaningless or not is_trade_talk:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  
전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강/과제용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 궁금해!" 📋
---"""
        else:
            with st.spinner("점장님이 장부를 확인하고 있습니다..."):
                stock_result, resp_type, final_cat = get_relevant_stock(user_input, st.session_state.last_category)
                st.session_state.last_category = final_cat
                stock_list = stock_result.to_dict('records')
                
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                고객의 질문: "{user_input}"
                [지침]
                1. 반드시 아래 [재고] 리스트에 있는 상품만 추천할 것.
                2. '💬 점장 추천' 항목에는 엑셀의 '점장 큐레이션' 내용과 함께, 왜 이 상품이 고객의 질문에 적합한지 전문가적인 이유를 덧붙여서 작성해.
                3. 가독성을 위해 각 줄 끝에 반드시 공백 두 개('  ')를 넣어 강제 줄바꿈을 적용해.
                4. 형식:
                   📍 모델명 : [상품명]  
                   ✨ 등 급 : [등급]  
                   💰 판매가 : [가격]  
                   🔋 배터리 : [배터리]  
                   💬 점장 추천 : [엑셀 내용 + 맞춤형 추천 이유]  
                   🎯 권장 용도 : [권장용도]  

                [재고]: {stock_list}
                [상황]: {resp_type}"""

                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.4
                ).choices[0].message.content
                
                final_stock_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]

        st.markdown(response)
        if final_stock_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_stock_df)
        
        st.session_state.messages.append({"role": "assistant", "content": response, "df": final_stock_df})
