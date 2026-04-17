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
    except:
        return None

df = load_inventory()

# --- 3. 사이드바 (항상 노출) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# --- 4. 검색 로직 ---
def get_relevant_stock(query, last_cat):
    if df is None: return pd.DataFrame(), "none", last_cat
    current_cat = last_cat
    if any(kw in query for kw in ["워치", "시계", "수영", "운동"]): current_cat = "애플워치"
    elif any(kw in query for kw in ["폰", "아이폰"]): current_cat = "아이폰"
    elif any(kw in query for kw in ["맥북", "노트북"]): current_cat = "맥북"
    
    cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
    q_words = query.split()
    filtered_df = cat_df.copy()
    matched = False
    for word in q_words:
        if len(word) > 1 and word not in ["추천", "있어", "보여줘"]:
            mask = filtered_df['상품명 (정제형)'].str.contains(word, case=False, na=False)
            if mask.any():
                filtered_df = filtered_df[mask]
                matched = True
    
    if filtered_df.empty or not matched:
        return cat_df.sort_values(by='판매가', ascending=False).head(3), "alternative", current_cat
    return filtered_df.head(3), "recommend", current_cat

# --- 5. 대화 엔진 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [수정] 등급 관련 질문 감지 로직 강화
        is_grade_query = any(kw in q_clean for kw in ["등급", "S급", "A급", "B급", "상태"])
        
        # 상담 관련 키워드
        trade_keywords = ["추천", "가성비", "가격", "시세", "운동", "수영", "작업", "인강", "있어", "매물", "재고"]
        is_trade_talk = any(kw in user_input for kw in trade_keywords) or is_grade_query

        if len(q_clean) < 2 and not is_grade_query:
            response = "고객님, 질문을 조금만 더 자세히 말씀해 주시겠어요? 😊"
        
        # 1순위: 등급 기준만 물어본 경우 (가이드 멘트 대신 즉시 답변)
        elif is_grade_query and not any(kw in user_input for kw in ["추천", "있어", "얼마"]):
            response = """고객님! 보상나라의 등급 기준을 안내해 드립니다! 😊  \n\n✨ **보상나라 등급 기준** \n\n* **S 등급**: 신품급! 선물용으로 가장 인기가 많아요. 🎁  \n* **A 등급**: 아주 미세한 사용감만 있는 가성비 원탑! ✨  \n* **B 등급**: 외관에 생활 기스가 있지만 기능은 완벽해요. 💯  \n* **가성비**: 외관 흔적은 좀 있지만 가격이 정말 착해요. 💪  \n* **진열상품**: 매장 전시용으로 배터리 상태가 아주 좋아요. 🚀"""
        
        # 2순위: 상품 검색
        elif is_trade_talk:
            with st.spinner("장부를 확인 중입니다..."):
                stock_result, resp_type, final_cat = get_relevant_stock(user_input, st.session_state.last_category)
                st.session_state.last_category = final_cat
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라' 점장이야. 
                1. 반드시 [재고] 리스트에 있는 상품만 추천해. 
                2. 줄바꿈을 위해 문장 끝에 반드시 공백 2개를 넣어라.
                3. '💬 점장 추천' 항목에는 엑셀 내용에 더해 "{user_input}"에 대한 맞춤 이유를 써라.
                4. 형식:
                   📍 모델명 : [상품명]  
                   ✨ 등 급 : [등급]  
                   💰 판매가 : [가격]  
                   🔋 배터리 : [배터리]  
                   💬 점장 추천 : [이유]  
                   🎯 권장 용도 : [용도]"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.4
                ).choices[0].message.content
                # [수정] 줄바꿈 강제 보정
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]
        
        # 3순위: 그 외 (가이드 멘트)
        else:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  \n전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!"""

        st.markdown(response)
        if 'final_df' in locals():
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
