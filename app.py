import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 (UI 유지) ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    .stTable { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">장부 확인 완료! 점장님이 직접 선별한 최적의 기기만 정직하게 추천합니다. ✨</p>', unsafe_allow_html=True)

# --- [2] 데이터 로드 로직 ---
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

# --- [3] 세션 상태 관리 (맥락 유지) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

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

# 이전 대화 렌더링
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
        
        # 키워드 체계 (상담 지속성 강화)
        grade_kw = ["등급", "기준", "상태"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "랩탑", "맥북에어", "맥북프로"]
        phone_kw = ["폰", "아이폰", "갤럭시", "핸드폰"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        action_kw = ["추천", "얼마", "재고", "저렴", "싼", "가성비", "금액", "가격", "있어", "있나요", "찾아"]
        context_kw = ["편집", "용도", "사용", "적합", "맞아", "응", "어", "괜찮", "좋아", "가능", "수도", "더", "무게", "배터리", "인강", "학교"]

        # 의도 분류
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (action_kw + context_kw))
        is_recommend_talk = any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + action_kw)) or \
                            (st.session_state.is_in_consult and any(kw in q_clean for kw in context_kw))

        response = ""
        final_df = None

        # CASE 1: 순수 등급 문의
        if is_grade_query:
            response = "보상나라 등급 기준을 안내해 드립니다! 😊\n\n- **S 등급**: 신품급\n- **A 등급**: 가성비 최고\n- **B 등급**: 실속형\n- **가성비/진열**: 실속파 최선택\n\n궁금하신 모델이 있으신가요?"
            st.session_state.is_in_consult = False

        # CASE 2: 제품 추천 및 상담 (핵심 영업 로직)
        elif is_recommend_talk:
            st.session_state.is_in_consult = True
            with st.spinner("장부를 확인 중입니다..."):
                # 카테고리 업데이트
                if any(kw in q_clean for kw in laptop_kw): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 재고 필터링 (가성비 우선 순위)
                if any(kw in q_clean for kw in ["저렴", "싼", "가성비", "더"]):
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    search_word = user_input.split()[0] if len(user_input.split()) > 0 else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                sys_prompt = f"""너는 '보상나라'의 노련하고 정직한 점장이야.
                [상담 원칙]
                1. 출시 정보 아는 척 금지: 고객이 찾는 특정 모델이 없을 때 "출시 전이다" 혹은 "나온 적 없다"고 단정하지 마. 
                   대신 "아쉽게도 현재 저희 매장 장부에는 해당 모델 재고가 확인되지 않네요."라고 답해.
                2. 적극적 대안 추천: 찾는 물건이 없을수록 "대신 지금 바로 추천드릴 수 있는 이런 기기들은 어떠세요?"라며 [오늘의 실제 재고]를 활용해 매끄럽게 영업해.
                3. 맥락 기억: 이전 대화에서 언급된 {st.session_state.last_category}를 끝까지 기억해서 "편집도 충분하죠", "가벼워서 좋아요" 같이 구어체로 답해.
                4. 사람 냄새 나는 문투: "적합합니다", "장점은 다음과 같습니다" 같은 딱딱한 말투 금지. 점장님이 직접 추천해주는 친근한 말투를 써.
                5. 필드명(카테고리:, 판매가:) 노출 금지 및 재고 데이터 기반 답변 엄수.
                
                [오늘의 실제 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.5
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)

        # CASE 3: 무의미한 입력 가이드 리스트 (누락 방지)
        else:
            response = """고객님, 말씀하신 내용을 점장님이 이해하지 못했어요. 😅  
            
**💡 점장님에게 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 맥북** 있어?" 💻
- "**아이폰 15 Pro** 재고 확인해줘" 📸
- "보상나라 **등급 기준**이 뭐야?" 📋"""
            st.session_state.is_in_consult = False

        # 최종 출력 및 세션 저장
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
