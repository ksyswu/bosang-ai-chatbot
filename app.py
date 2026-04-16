import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- [중요] Groq API 키 설정 ---
# 깃허브에 올릴 때 보안을 위해 streamlit의 secrets 기능을 사용합니다.
# 로컬 테스트 시에는 Groq 사이트에서 받은 키를 아래 " " 안에 잠시 넣으셔도 되지만,
# 깃허브에 올리기 전에는 반드시 아래처럼 st.secrets 코드로 복구해 주세요.
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    # 로컬 테스트용
    GROQ_API_KEY = ""

client = Groq(api_key=GROQ_API_KEY)

# --- 2. 데이터 로드 ---
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

def get_relevant_stock(query, category):
    if df is None: return [], "none"
    cat_df = df[df['카테고리'].str.contains(category, na=False)].copy()
    target_col = next((c for c in ['상품명 (정제형)', '상세모델', '상품명', '모델명'] if c in cat_df.columns), cat_df.columns[0])
    
    usage_keywords = ["인강", "프로그래밍", "개발", "게임", "편집", "사무", "과제", "넷플릭스", "유튜브", "운동"]
    is_usage_search = any(uk in query for uk in usage_keywords)
    
    q_words = query.split()
    filtered_df = cat_df.copy()
    has_match = False
    
    grade_keywords = [word for word in ["S등급", "A등급", "B등급", "S급", "A급", "B급"] if word in query.replace(" ", "")]
    for gk in grade_keywords:
        grade_letter = gk[0]
        if '등급' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['등급'].str.contains(grade_letter, case=False, na=False)]
            has_match = True

    for word in q_words:
        if len(word) > 0 and word not in usage_keywords + ["가장", "저렴한", "추천", "S등급", "A등급", "B등급", "S급", "A급", "B급"]:
            match_mask = filtered_df[target_col].str.contains(word, case=False, na=False)
            if match_mask.any():
                filtered_df = filtered_df[match_mask]
                has_match = True
    
    if not has_match and not is_usage_search:
        return cat_df.sort_values(by='판매가', ascending=False).head(5), "alternative"
    
    sort_asc = any(kw in query for kw in ["저렴", "싼", "최저가", "가성비"])
    final_df = filtered_df if not filtered_df.empty else cat_df
    return final_df.sort_values(by='판매가', ascending=sort_asc).head(5), "recommend"

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_query := st.chat_input("점장님에게 편하게 물어보세요!"):
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        q_clean = user_query.replace(" ", "")
        
        is_pure_grade_query = any(kw in q_clean for kw in ["등급기준", "등급이뭐야", "상태차이"]) and not any(kw in q_clean for kw in ["추천", "저렴", "싼", "있어", "보여줘"])
        
        current_cat = None
        if any(kw in q_clean for kw in ["폰", "아이폰"]): current_cat = "아이폰"
        elif any(kw in q_clean for kw in ["맥북", "노트북"]): current_cat = "맥북"
        elif any(kw in q_clean for kw in ["패드", "아이패드"]): current_cat = "아이패드"
        elif any(kw in q_clean for kw in ["워치", "애플워치"]): current_cat = "애플워치"
        if current_cat: st.session_state.last_category = current_cat

        trade_keywords = ["추천", "가성비", "시세", "얼마", "가격", "사양", "사진", "카메라", "화질", "게임", "배터리", "운동", "작업", "넷플릭스", "저렴", "싼", "프로그래밍", "개발", "편집", "인강", "과제"]
        is_trade_talk = current_cat is not None or any(kw in q_clean for kw in trade_keywords) or any(kw in q_clean for kw in ["S급", "A급", "B급", "등급"])

        if is_pure_grade_query:
            response = """고객님! 보상나라의 꼼꼼한 등급 기준이 궁금하시군요? 😊\n\n✨ **보상나라 등급 기준 안내**\n* **S 등급**: 신품급! 선물용 강추! 🎁\n* **A 등급**: 깔끔함. 미세 흔적 있지만 가성비 최고 ✨\n* **B 등급**: 생활 기스 있음. 기능은 완벽 💯\n* **가성비**: 찍힘 등 외관 흔적 있음. (실속파용) 💪\n* **진열상품**: 매장 전시용. 배터리 효율 최상 🚀"""
        elif not is_trade_talk:
            response = "어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅\n\n아이폰/맥북 추천이나 시세, 등급 기준에 대해 물어봐주세요!"
        else:
            with st.spinner("점장님이 매물을 선별하고 있습니다..."):
                stock_result, response_type = get_relevant_stock(user_query, st.session_state.last_category)
                stock_list = stock_result.to_dict('records')
                for item in stock_list:
                    item['판매가_표기'] = "{:,}".format(int(item.get('판매가', 0)))

                # Groq을 이용한 답변 생성 (Gemma 2 9b 모델 사용)
                completion = client.chat.completions.create(
                    model="gemma2-9b-it",
                    messages=[
                        {"role": "system", "content": f"너는 보상나라의 베테랑 점장이야. [상황 분석]: 응답 유형 {response_type}, 고객 질문 {user_query}. 실시간 재고 데이터 {stock_list}를 바탕으로 고객 질문 의도에 딱 맞는 맞춤형 큐레이션을 제공해. 엑셀의 큐레이션은 참고만 하고 네가 직접 용도에 맞춰서 작성해. 재고에 없는 정보는 절대 지어내지 마."},
                        {"role": "user", "content": user_query}
                    ],
                    temperature=0.7,
                )
                ai_output = completion.choices[0].message.content
                response = ai_output.replace("#", "").replace("\n", "\n\n")

        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})