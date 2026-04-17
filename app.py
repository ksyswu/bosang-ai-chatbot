import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">정직한 점장님이 장부에 있는 실재고만 정확히 추천해 드립니다. ✨</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 ---
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

# --- [3] 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

# --- [4] 사이드바 (등급 기준 고정) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# 이전 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(msg["df"])

# --- [5] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 확장 (노트북/컴퓨터 -> 맥북 매칭)
        grade_kw = ["등급", "기준", "상태", "s급", "a급", "b급", "가성비", "진열"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑", "맥북에어", "맥북프로"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "애플워치"]
        
        # 의도 분류
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in ["추천", "얼마", "재고", "있어"])
        is_meaningful = any(kw in q_clean for kw in (grade_kw + laptop_kw + phone_kw + pad_kw + watch_kw + ["추천", "가격", "저렴"]))

        response = ""
        final_df = None

        if is_grade_query:
            response = "보상나라의 등급 기준입니다! 😊\n\n- **S 등급**: 신품급 🎁\n- **A 등급**: 미세흔적 가성비 ✨\n- **B 등급**: 생활기스 실속형 💯\n- **가성비/진열**: 실속파 최선택 💪"
        
        elif not is_meaningful:
            response = "고객님, 말씀하신 내용을 잘 이해하지 못했어요. 😅\n\n**💡 이렇게 질문해 보세요!**\n1. '인강용 **저렴한 맥북** 있어?' 💻\n2. '사진 잘 나오는 **아이폰 15 Pro** 재고 확인해줘' 📸\n3. '보상나라 **등급 기준**이 뭐야?' 📋"

        else:
            with st.spinner("장부를 확인하고 있습니다..."):
                # 카테고리 강제 매칭 로직
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                elif any(kw in q_clean for kw in watch_kw): st.session_state.last_category = "애플워치"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 가격순 정렬 (저렴한 것 찾을 때)
                if any(kw in q_clean for kw in ["저렴", "싼", "가격", "가성비"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    stock_result = cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라' 점장이야. 
                [상담 절대 원칙]
                1. 노트북을 물으면 반드시 [장부 데이터]의 맥북(MacBook)을 추천해. "추천할 수 없다"는 말은 절대 금지야.
                2. 질문과 상관없는 기기(예: 노트북 묻는데 아이폰)를 끼워 팔지 마. 매우 무례한 행동이야.
                3. "구매 예약", "관심 있으신가요?" 같은 기계적인 멘트는 삭제해. 우리 챗봇은 상담 전용이야.
                4. 전문가로서 장부 데이터의 모델이 왜 해당 용도(인강, 편집 등)에 좋은지 설명하고 대화를 마무리해.
                5. 필드명(카테고리:, 판매가:) 노출 금지.
                
                [오늘의 실재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.3
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명', '등급', '판매가', '배터리']].reset_index(drop=True) if not stock_result.empty else None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
