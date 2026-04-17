import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 제목 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: bold; color: #1E1E1E; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #666; margin-bottom: 25px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">장부 확인 완료! 점장님이 직접 선별한 최고의 기기만 추천합니다. ✨</p>', unsafe_allow_html=True)

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

# --- 3. 세션 상태 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 (등급 기준) ---
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

# --- 5. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 정의
        grade_kw = ["등급", "기준", "상태", "s급", "a급", "b급", "가성비", "진열"]
        product_kw = ["폰", "아이폰", "패드", "아이패드", "워치", "맥북", "노트북"]
        trade_kw = ["추천", "가격", "재고", "얼마", "저렴", "싼", "있어", "구매", "더"]
        purpose_kw = ["촬영", "사진", "유튜브", "게임", "인강", "세컨", "운동", "필기", "작업", "일상", "공부", "학습"]

        # 의도 분류
        is_grade_query = any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in trade_kw)
        is_recommend_talk = any(kw in q_clean for kw in (product_kw + trade_kw + purpose_kw)) or st.session_state.waiting_for_purpose or q_clean in ["응", "어", "맞아", "좋아"]

        response = ""
        final_df = None

        # [CASE 1] 등급 문의
        if is_grade_query:
            response = "보상나라의 등급 기준입니다! 😊\n\n- **S 등급**: 신품급 선물용 🎁\n- **A 등급**: 깔끔한 가성비 ✨\n- **B 등급**: 생활기스 실속형 💯\n- **가성비/진열**: 가격 혜택 극대화 💪"
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 제품 추천 및 상담 (핵심 영업 로직)
        elif is_recommend_talk:
            with st.spinner("점장님이 장부를 확인 중입니다..."):
                # 카테고리 업데이트
                if any(kw in q_clean for kw in ["워치", "애플워치"]): st.session_state.last_category = "애플워치"
                elif any(kw in q_clean for kw in ["폰", "아이폰"]): st.session_state.last_category = "아이폰"
                elif any(kw in q_clean for kw in ["맥북", "노트북"]): st.session_state.last_category = "맥북"
                elif any(kw in q_clean for kw in ["패드", "아이패드"]): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # '더 저렴한 것' 요청 시 가격순 정렬 후 추천
                if "저렴" in q_clean or "싼" in q_clean or "가격" in q_clean:
                    stock_result = cat_df.sort_values(by='판매가').head(2)
                else:
                    search_word = user_input.split()[0] if not st.session_state.waiting_for_purpose else ""
                    target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                    stock_result = target_stock.head(2) if not target_stock.empty else cat_df.head(2)
                
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [강화된 전문가 프롬프트]
                sys_prompt = f"""너는 '보상나라'의 친근하고 능력 있는 점장이야. 
                [상담 절대 수칙]
                1. 답변에 "카테고리:", "상세모델:", "상품명:", "점장 큐레이션:" 같은 단어를 절대 쓰지 마. 장부를 읽어주는 게 아니라 '상담'을 해줘.
                2. 엑셀의 추천 포인트를 바탕으로, 왜 이 제품이 고객에게 딱인지 점장으로서의 '추론'과 '의견'을 덧붙여서 말해.
                3. "적합하다고 생각하십니까?" 같은 기계적인 질문은 절대 하지 마. 대신 "이 모델이 고객님께 최고의 선택이 될 겁니다"라고 확신을 줘.
                4. 재고가 없는 제품(아이폰 17 등)은 "현재 장부에 없다"고 말하고 바로 있는 재고로 유도해.
                5. 고객이 "응"이라고 하면 대화를 종결하지 말고, 구매를 돕기 위한 추가 멘트(예: "더 궁금하신 점이나 예약 도와드릴까요?")를 던져.
                
                [오늘의 추천 재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.4
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']]
                
                # 용도 질문 중복 체크
                if not any(kw in q_clean for kw in purpose_kw) and not st.session_state.waiting_for_purpose:
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # [CASE 3] 의미 없는 입력 -> 질문 가이드
        else:
            response = """고객님, 말씀하신 내용을 제가 잘 이해하지 못했어요. 😅  
            점장님에게 이렇게 물어보시면 딱 맞는 제품을 찾아드릴게요!
            
---
**💡 질문 예시**
1. "사진 잘 나오는 **아이폰 15 Pro** 있어?" 📸
2. "인강용 **저렴한 아이패드** 추천해줘" 📝
3. "보상나라 **등급 기준**이 뭐야?" 📋
---"""

        # 최종 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기"):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
