import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 사이드바 등급 안내 ---
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

# --- 3. Groq API 및 데이터 로드 ---
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = ""

client = Groq(api_key=GROQ_API_KEY)

@st.cache_data
def load_inventory():
    file_name = "inventory.xlsx"
    try:
        df = pd.read_excel(file_name, sheet_name='Sheet1')
        df.columns = [str(c).strip() for c in df.columns]
        # 판매가 숫자 변환 및 콤마 표기 미리 생성
        df['판매가'] = pd.to_numeric(df['판매가'], errors='coerce').fillna(0)
        df['판매가_표기'] = df['판매가'].apply(lambda x: "{:,}원".format(int(x)))
        # 배터리 미리 %로 변환 (AI 전달용)
        if '배터리' in df.columns:
            df['배터리_표기'] = pd.to_numeric(df['배터리'], errors='coerce').apply(
                lambda x: f"{int(x * 100)}%" if pd.notnull(x) and x <= 1 else (f"{int(x)}%" if pd.notnull(x) else "정보없음")
            )
        return df
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return None

df = load_inventory()

# --- 4. 재고 검색 로직 (엄격한 필터링) ---
def get_relevant_stock(query, category):
    if df is None: return pd.DataFrame(), "none"
    cat_df = df[df['카테고리'].str.contains(category, na=False)].copy()
    target_col = '상품명 (정제형)'
    
    q_words = query.split()
    filtered_df = cat_df.copy()
    
    # 등급 필터링
    grade_letter = None
    for gk in ["S급", "A급", "B급", "S등급", "A등급", "B등급"]:
        if gk in query.replace(" ", ""):
            grade_letter = gk[0]
            break
    if grade_letter:
        filtered_df = filtered_df[filtered_df['등급'].str.contains(grade_letter, case=False, na=False)]

    # 키워드 필터링
    matched = False
    for word in q_words:
        if len(word) > 1 and word not in ["추천", "있어", "보여줘", "가장", "저렴한"]:
            mask = filtered_df[target_col].str.contains(word, case=False, na=False)
            if mask.any():
                filtered_df = filtered_df[mask]
                matched = True
    
    # 검색 결과가 없으면 해당 카테고리 전체에서 추천
    if filtered_df.empty or not matched:
        return cat_df.sort_values(by='판매가', ascending=False).head(3), "alternative"
    
    return filtered_df.sort_values(by='판매가', ascending=True).head(3), "recommend"

# --- 5. 대화 내역 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "stock_df" in message and message["stock_df"] is not None:
            with st.expander("📦 추천 상품 목록 다시보기"):
                st.dataframe(message["stock_df"])

# --- 6. 실시간 상담 엔진 ---
if user_query := st.chat_input("점장님에게 편하게 물어보세요!"):
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        q_clean = user_query.replace(" ", "")
        if any(kw in q_clean for kw in ["폰", "아이폰", "핸드폰"]): st.session_state.last_category = "아이폰"
        elif any(kw in q_clean for kw in ["맥북", "노트북"]): st.session_state.last_category = "맥북"
        elif any(kw in q_clean for kw in ["패드", "아이패드"]): st.session_state.last_category = "아이패드"

        with st.spinner("점장님이 매물을 선별 중입니다..."):
            stock_result, response_type = get_relevant_stock(user_query, st.session_state.last_category)
            
            # AI와 표가 사용할 데이터를 동일하게 확정
            display_cols = ['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '점장 큐레이션 (추천포인트)', '권장용도']
            final_stock_df = stock_result[display_cols]
            stock_json = final_stock_df.to_dict('records')

            # 시스템 프롬프트: 가독성(줄바꿈) 및 데이터 일치 강제
            sys_prompt = f"""너는 '보상나라'의 10년차 베테랑 점장이야. 
            [중요 규칙]
            1. 제공된 [실시간 재고] 리스트에 없는 모델은 절대 추천하거나 언급하지 마. (환각 금지)
            2. 가독성을 위해 항목마다 반드시 줄바꿈을 두 번씩 해서 시원하게 보여줘.
            3. 답변은 반드시 아래 형식을 지켜:

            고객님! 찾으시는 상품 여기 있습니다! 😊

            📍 모델명 : [상품명 (정제형)]
            ✨ 등 급 : [등급]
            💰 판매가 : [판매가_표기]
            🔋 배터리 : [배터리_표기]
            💬 점장 추천 : [점장 큐레이션 (추천포인트)]
            🎯 권장 용도 : [권장용도]

            [실시간 재고 데이터]: {stock_json}
            [응답 유형]: {response_type} (alternative면 "아쉽게도 찾는 모델은 없지만 대안을 추천합니다"라고 말해)
            """

            try:
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages[-3:],
                    temperature=0.3 # 일관성을 위해 온도를 낮춤
                )
                response = completion.choices[0].message.content
            except Exception as e:
                response = f"점장님이 잠시 자리를 비웠네요. (에러: {e})"

        st.markdown(response)
        
        with st.expander("📦 추천 상품 목록 확인하기"):
            st.dataframe(final_stock_df)

        st.session_state.messages.append({"role": "assistant", "content": response, "stock_df": final_stock_df})
