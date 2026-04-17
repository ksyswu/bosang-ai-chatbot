import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 ---
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

# --- 3. 검색 로직 (카테고리 매칭 및 결과 제한) ---
def get_relevant_stock(query, last_cat):
    if df is None: return pd.DataFrame(), "none", last_cat
    
    # 키워드 기반 카테고리 판별
    current_cat = last_cat
    if any(kw in query for kw in ["워치", "시계", "수영", "운동"]): current_cat = "애플워치"
    elif any(kw in query for kw in ["폰", "아이폰"]): current_cat = "아이폰"
    elif any(kw in query for kw in ["맥북", "노트북", "코딩", "프로그래밍"]): current_cat = "맥북"
    elif any(kw in query for kw in ["패드", "아이패드"]): current_cat = "아이패드"

    # 해당 카테고리만 필터링
    cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].copy()
    
    # 상세 모델 검색
    filtered_df = cat_df.copy()
    q_words = query.split()
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

# --- 4. 대화 엔진 및 프롬프트 ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

# 이전 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# 채팅 입력
if user_input := st.chat_input("수영용 워치 추천해줘!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        stock_result, resp_type, final_cat = get_relevant_stock(user_input, st.session_state.last_category)
        st.session_state.last_category = final_cat
        
        # 엑셀 데이터 준비
        stock_list = stock_result.to_dict('records')
        
        # [전문가 포인트] AI에게 큐레이션 이유를 직접 생성하도록 지시
        sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
        고객의 질문: "{user_input}"

        [지침]
        1. 반드시 아래 [재고] 리스트에 있는 상품만 추천할 것.
        2. '💬 점장 추천' 항목에는 엑셀의 '점장 큐레이션' 내용과 함께, 
           **왜 이 상품이 고객의 질문({user_input})에 적합한지** 전문가적인 이유를 덧붙여서 작성해.
        3. 가독성을 위해 각 줄 끝에 '  '(공백 두 개)를 넣어 강제 줄바꿈을 적용해.
        4. 형식:
           📍 모델명 : [상품명]  
           ✨ 등 급 : [등급]  
           💰 판매가 : [가격]  
           🔋 배터리 : [배터리]  
           💬 점장 추천 : [엑셀 내용 + 맞춤형 추천 이유]  
           🎯 권장 용도 : [권장용도]  
           (다음 상품과 사이에는 반드시 한 줄을 비워라)

        [재고]: {stock_list}
        [상황]: {resp_type}"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": sys_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
            temperature=0.4
        ).choices[0].message.content

        st.markdown(response)
        
        # 목록 출력 (AI가 추천한 데이터와 100% 동일한 필터링 결과)
        display_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]
        with st.expander("📦 추천 상품 목록 확인하기"):
            st.dataframe(display_df)
        
        st.session_state.messages.append({"role": "assistant", "content": response, "df": display_df})
