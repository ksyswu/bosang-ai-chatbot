import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 사이드바 등급 안내 (상시 노출) ---
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
        df['판매가'] = pd.to_numeric(df['판매가'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return None

df = load_inventory()

# --- 4. 재고 검색 로직 ---
def get_relevant_stock(query, category):
    if df is None: return [], "none"
    cat_df = df[df['카테고리'].str.contains(category, na=False)].copy()
    
    # 검색 대상 컬럼 (엑셀 기준)
    target_col = '상품명 (정제형)' if '상품명 (정제형)' in cat_df.columns else cat_df.columns[1]
    
    q_words = query.split()
    filtered_df = cat_df.copy()
    has_match = False
    
    # 등급 필터링
    grade_keywords = [word for word in ["S등급", "A등급", "B등급", "S급", "A급", "B급"] if word in query.replace(" ", "")]
    for gk in grade_keywords:
        grade_letter = gk[0]
        if '등급' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['등급'].str.contains(grade_letter, case=False, na=False)]
            has_match = True

    # 키워드 검색
    for word in q_words:
        if len(word) > 1 and word not in ["가장", "저렴한", "추천", "보여줘", "있어"]:
            match_mask = filtered_df[target_col].str.contains(word, case=False, na=False)
            if match_mask.any():
                filtered_df = filtered_df[match_mask]
                has_match = True
    
    if not has_match:
        return cat_df.sort_values(by='판매가', ascending=False).head(3), "alternative"
    
    return filtered_df.sort_values(by='판매가', ascending=True).head(3), "recommend"

# --- 5. 대화 내역 관리 (Memory) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. 실시간 상담 엔진 ---
if user_query := st.chat_input("점장님에게 편하게 물어보세요!"):
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        q_clean = user_query.replace(" ", "")
        
        # 등급 기준 질문
        is_pure_grade_query = any(kw in q_clean for kw in ["등급기준", "등급이뭐야", "상태차이"]) and not any(kw in q_clean for kw in ["추천", "저렴", "보여줘"])
        
        # 카테고리 판단
        current_cat = None
        if any(kw in q_clean for kw in ["폰", "아이폰"]): current_cat = "아이폰"
        elif any(kw in q_clean for kw in ["맥북", "노트북"]): current_cat = "맥북"
        elif any(kw in q_clean for kw in ["패드", "아이패드"]): current_cat = "아이패드"
        elif any(kw in q_clean for kw in ["워치", "애플워치"]): current_cat = "애플워치"
        if current_cat: st.session_state.last_category = current_cat

        trade_keywords = ["추천", "가성비", "시세", "얼마", "가격", "사양", "카메라", "게임", "배터리", "운동", "작업", "저렴", "싼", "있어"]
        is_trade_talk = current_cat is not None or any(kw in q_clean for kw in trade_keywords) or any(kw in q_clean for kw in ["S급", "A급", "B급"])

        if is_pure_grade_query:
            response = """고객님! 보상나라의 등급 기준은 이렇습니다! 😊  
✨ **보상나라 등급 기준 안내**
* **S 등급**: 신품급! 선물용 강추! 🎁
* **A 등급**: 깔끔함. 미세 흔적 가성비 최고 ✨
* **B 등급**: 생활 기스 있음. 기능은 완벽 💯
* **가성비**: 찍힘 등 외관 흔적 있음. (실속파용) 💪
* **진열상품**: 매장 전시용. 배터리 효율 최상 🚀"""

        elif not is_trade_talk:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  
전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강/과제용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 궁금해!" 📋
---"""

        else:
            with st.spinner("점장님이 매물을 선별하고 있습니다..."):
                stock_result, response_type = get_relevant_stock(user_query, st.session_state.last_category)
                stock_list = stock_result.to_dict('records')
                for item in stock_list:
                    item['판매가_표기'] = "{:,}".format(int(item.get('판매가', 0)))

                # AI 점장 큐레이션 특화 지침
                chat_context = [
                    {"role": "system", "content": f"""너는 보상나라의 10년 경력 베테랑 점장이야. 
                    제공된 [실시간 재고] 데이터의 '점장 큐레이션 (추천포인트)'과 '권장용도'를 반드시 활용해서 전문가답게 추천해줘.
                    손님에게 옆에서 설명해주는 것처럼 친근하고 신뢰감 있게 말해줘.
                    [실시간 재고]: {stock_list}
                    [응답 유형]: {response_type}"""}
                ]
                for msg in st.session_state.messages[-3:]:
                    chat_context.append(msg)

                try:
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=chat_context,
                        temperature=0.7,
                    )
                    response = completion.choices[0].message.content
                except Exception as e:
                    response = f"죄송합니다, 잠시 통신 에러가 발생했어요. (에러: {e})"

        st.markdown(response)
        
        if is_trade_talk and not stock_result.empty:
            with st.expander("📦 추천 상품 목록 확인하기"):
                # 엑셀의 실제 컬럼명에 맞춰 안전하게 출력
                display_cols = [c for c in ['상품명 (정제형)', '등급', '판매가_표기', '배터리', '권장용도'] if c in stock_result.columns]
                st.dataframe(stock_result[display_cols])

        st.session_state.messages.append({"role": "assistant", "content": response})
