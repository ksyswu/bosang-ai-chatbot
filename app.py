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
        # 가격 및 배터리 전처리
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

# --- 4. 재고 검색 로직 ---
def get_relevant_stock(query, category):
    if df is None: return pd.DataFrame(), "none"
    cat_df = df[df['카테고리'].str.contains(category, na=False)].copy()
    target_col = '상품명 (정제형)'
    
    q_words = query.split()
    filtered_df = cat_df.copy()
    
    grade_letter = None
    for gk in ["S급", "A급", "B급", "S등급", "A등급", "B등급"]:
        if gk in query.replace(" ", ""):
            grade_letter = gk[0]
            break
    if grade_letter:
        filtered_df = filtered_df[filtered_df['등급'].str.contains(grade_letter, case=False, na=False)]

    matched = False
    for word in q_words:
        if len(word) > 1 and word not in ["추천", "있어", "보여줘", "가장", "저렴한"]:
            mask = filtered_df[target_col].str.contains(word, case=False, na=False)
            if mask.any():
                filtered_df = filtered_df[mask]
                matched = True
    
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
        
        # 등급 기준 질문 여부
        is_pure_grade_query = any(kw in q_clean for kw in ["등급기준", "등급이뭐야", "상태차이"]) and not any(kw in q_clean for kw in ["추천", "저렴", "보여줘"])
        
        # 카테고리 판단
        current_cat = None
        if any(kw in q_clean for kw in ["폰", "아이폰", "핸드폰"]): current_cat = "아이폰"
        elif any(kw in q_clean for kw in ["맥북", "노트북"]): current_cat = "맥북"
        elif any(kw in q_clean for kw in ["패드", "아이패드"]): current_cat = "아이패드"
        elif any(kw in q_clean for kw in ["워치", "애플워치"]): current_cat = "애플워치"
        if current_cat: st.session_state.last_category = current_cat

        # 상담 관련 키워드 체크
        trade_keywords = ["추천", "가성비", "시세", "얼마", "가격", "사양", "카메라", "게임", "배터리", "운동", "작업", "저렴", "싼", "있어", "매물", "재고"]
        is_trade_talk = current_cat is not None or any(kw in q_clean for kw in trade_keywords) or any(kw in q_clean for kw in ["S급", "A급", "B급"])

        final_stock_df = None

        # [1] 등급 기준 답변
        if is_pure_grade_query:
            response = """고객님! 보상나라의 등급 기준은 이렇습니다! 😊  \n\n✨ **보상나라 등급 기준 안내**\n* **S 등급**: 신품급! 선물용 강추! 🎁\n* **A 등급**: 깔끔함. 미세 흔적 가성비 최고 ✨\n* **B 등급**: 생활 기스 있음. 기능은 완벽 💯\n* **가성비**: 찍힘 등 외관 흔적 있음. (실속파용) 💪\n* **진열상품**: 매장 전시용. 배터리 효율 최상 🚀"""

        # [2] 가이드 멘트 (질문이 모호할 때)
        elif not is_trade_talk:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  
전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강/과제용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 궁금해!" 📋
---"""

        # [3] 상품 추천 답변
        else:
            with st.spinner("점장님이 장부를 확인하고 있습니다..."):
                stock_result, response_type = get_relevant_stock(user_query, st.session_state.last_category)
                
                display_cols = ['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '점장 큐레이션 (추천포인트)', '권장용도']
                final_stock_df = stock_result[display_cols].copy()
                
                stock_info_text = ""
                for i, row in final_stock_df.iterrows():
                    stock_info_text += f"- 상품명: {row['상품명 (정제형)']}, 등급: {row['등급']}, 가격: {row['판매가_표기']}, 배터리: {row['배터리_표기']}, 큐레이션: {row['점장 큐레이션 (추천포인트)']}, 용도: {row['권장용도']}\n"

                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                
                [규칙]
                1. [실시간 재고]에 있는 모델만 추천해. 없는 모델 언급 금지.
                2. 가독성을 위해 항목 사이에 반드시 줄바꿈을 두 번 넣어라.
                3. 답변 형식:
                   📍 모델명 : [상품명 (정제형)]
                   
                   ✨ 등 급 : [등급]
                   
                   💰 판매가 : [판매가_표기]
                   
                   🔋 배터리 : [배터리_표기]
                   
                   💬 점장 추천 : [점장 큐레이션 내용]
                   
                   🎯 권장 용도 : [권장용도]

                [실시간 재고]:
                {stock_info_text}

                [상황]: {response_type}
                """

                try:
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages[-3:],
                        temperature=0.3
                    )
                    response = completion.choices[0].message.content
                except Exception as e:
                    response = f"점장님이 잠시 자리를 비웠네요. (오류: {str(e)})"

        st.markdown(response)
        
        if final_stock_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_stock_df[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']])

        st.session_state.messages.append({"role": "assistant", "content": response, "stock_df": final_stock_df})
