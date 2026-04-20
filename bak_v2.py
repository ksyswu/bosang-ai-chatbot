import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 스타일 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #1E1E1E; }
    .sub-title { font-size: 15px; color: #666; margin-bottom: 20px; }
    .stTable { width: 100%; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="main-title">💻 보상나라 AI 점장님 실시간 상담</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">장부 확인 완료! 점장님이 직접 선별한 기기만 정직하게 추천합니다. ✨</p>', unsafe_allow_html=True)

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

# --- [3] 세션 관리 및 사이드바 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 가성비 최고 ✨
- **B 등급**: 생활 기스 있음 💯
- **가성비**: 실속파용 (기스 있음) 💪
- **진열상품**: 매장 전시용. 배터리 최상 🚀
    """)

guide_text = """
**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘"
- "**아이폰 15 Pro** S급 재고 있어?"
- "**영상편집용 맥북** 있어?"
"""

# 대화 로그 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

# 초기 접속 시 가이드 출력
if not st.session_state.messages:
    welcome_msg = f"반갑습니다! 보상나라 점장입니다. 😊 어떤 기기를 찾으시나요? 장부에서 상태 좋고 가격 착한 제품으로 딱 골라드릴게요!  \n{guide_text}"
    st.session_state.messages.append({"role": "assistant", "content": welcome_msg, "df": None})
    st.rerun()

# --- [4] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        # 키워드 체크 (의도 파악)
        is_grade = any(kw in q_clean for kw in ["등급", "상태", "기준", "급"])
        is_high_spec = any(kw in q_clean for kw in ["편집", "프로그래밍", "고사양", "성능", "개발", "영상", "작업"])
        is_low_price = any(kw in q_clean for kw in ["저렴", "싼", "가격", "얼마", "가성비"])
        
        laptop_kw = ["맥북", "노트북", "컴퓨터", "에어", "프로"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        is_context = any(kw in q_clean for kw in ["용도", "사용", "인강", "학교", "가능", "돼", "될까", "추천"])

        # A. 등급 기준 질문 (순수 등급만 물었을 때)
        if is_grade and not (any(kw in q_clean for kw in laptop_kw + phone_kw + pad_kw + watch_kw) or is_context or is_high_spec):
            response = "보상나라 등급 기준 안내해 드립니다! 😊  \n\n**S 등급**: 신품급 상태  \n**A 등급**: 흠집 없이 깔끔함  \n**B 등급**: 미세 생활 기스  \n**가성비**: 기능 정상, 외관 기스 있음  \n**진열상품**: 전시 모델, 배터리 최상급"
            final_df = None

        # B. 제품 추천 및 상담 (핵심 로직)
        elif any(kw in q_clean for kw in laptop_kw + phone_kw + pad_kw + watch_kw) or is_context or is_high_spec or is_low_price:
            with st.spinner("장부 확인 중..."):
                # 1. 카테고리 결정 및 유지
                if any(kw in q_clean for kw in watch_kw): cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): cat = "아이폰"
                else: cat = st.session_state.last_category
                st.session_state.last_category = cat

                # 2. 데이터 필터링 및 전략적 정렬
                f_df = df[df['카테고리'].str.contains(cat, na=False)]
                
                # [중요] 고사양 요구 시 무조건 가격 높은(성능 좋은) 순, 저렴 요구 시 낮은 순 정렬
                if is_high_spec:
                    f_df = f_df.sort_values(by='판매가', ascending=False)
                elif is_low_price:
                    f_df = f_df.sort_values(by='판매가', ascending=True)
                else:
                    # 기본적으로는 성능/상태가 좋은 상위 모델 우선 노출
                    f_df = f_df.sort_values(by='판매가', ascending=False)
                
                stock_result = f_df.head(3)
                stock_list = stock_result.to_dict('records')

                # [에러 방지] AI 전달용 클린 히스토리 (메시지 5개 유지)
                clean_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]]

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # 시스템 프롬프트: 지침 유출 방지 및 논리 강화
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [핵심 규칙]
                1. 추천 일치: 반드시 현재 제공된 재고({stock_list}) 중 '첫 번째' 모델을 메인으로 추천해.
                2. 논리적 유연성: 손님이 "프로그래밍", "영상편집" 같은 고사양을 물으면, 이전 대화에서 저렴한 모델을 찾았더라도 과감히 성능 좋은 모델로 상향 추천해. 
                3. "무조건 돼요" 금지: 저사양 모델(예: 2017년식)로 고사양 작업이 어렵다면 솔직하게 말하고, 리스트 내의 더 고사양 모델을 권유해.
                4. 지침 비노출: '지침', '재고 리스트', '단일 모델' 같은 단어는 절대 쓰지 마.
                
                [양식]
                고객님이 말씀하신 용도에 딱 맞는 보상나라 베스트 매물을 골라봤습니다!
                📍 모델명 : [모델명]
                ✨ 등 급 : [등급]
                💰 판매가 : [판매가]
                🔋 배터리 상태 : [배터리 표기]
                💬 점장 큐레이션 : "[전문가 추천사]"
                """

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + clean_history,
                    temperature=0.0 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        else:
            response = f"죄송합니다, 손님! 질문을 정확히 이해하지 못했어요. 아래 예시처럼 말씀해주시면 바로 찾아드릴게요!  \n{guide_text}"
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
