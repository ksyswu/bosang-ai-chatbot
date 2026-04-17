import streamlit as st
import pandas as pd
from groq import Groq

# --- [1] 페이지 설정 및 제목 ---
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
if "is_in_consult" not in st.session_state:
    st.session_state.is_in_consult = False

with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
- **S 등급**: 신품급! 선물용 강추! 🎁
- **A 등급**: 깔끔함. 가성비 최고 ✨
- **B 등급**: 생활 기스 있음 💯
- **가성비**: 실속파용 (기스/찍힘 있음) 💪
- **진열상품**: 매장 전시용. 배터리 최상 🚀
    """)

# [질문 제안 리스트] - 못 알아들었을 때 및 초기 화면용
guide_text = """
**💡 이렇게 물어보시면 빨라요!**
- "인강용 **저렴한 아이패드** 추천해줘"
- "**아이폰 15 Pro** S급 재고 있어?"
- "**운동용 애플워치** 추천해줘"
"""

# 채팅 로그 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(msg["df"])

# [최초 접속 시 인사말 자동 출력]
if not st.session_state.messages:
    welcome_msg = f"반갑습니다! 보상나라 점장입니다. 😊 어떤 기기를 찾으시나요? 장부에서 상태 좋고 가격 착한 녀석들로 딱 골라드릴게요!  \n{guide_text}"
    st.session_state.messages.append({"role": "assistant", "content": welcome_msg, "df": None})
    st.rerun()

# --- [4] 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요!"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "").lower()
        
        grade_kw = ["등급", "상태", "기준", "급"]
        laptop_kw = ["맥북", "노트북", "컴퓨터", "프로", "에어"]
        phone_kw = ["폰", "아이폰", "갤럭시"]
        pad_kw = ["패드", "아이패드", "태블릿"]
        watch_kw = ["워치", "시계", "애플워치"]
        context_kw = ["편집", "용도", "사용", "적합", "인강", "학교", "성능", "게임", "프로그래밍", "개발", "그림", "드로잉", "가능", "돼", "될까"]

        # A. 등급 기준 질문 (가이드 노출 없음)
        if any(kw in q_clean for kw in grade_kw) and not any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + context_kw)):
            response = """보상나라의 등급 기준을 안내해 드립니다! 😊

**S 등급**: 신품급 상태 (선물용 추천)  
**A 등급**: 흠집 없이 깔끔함 (인기 최고)  
**B 등급**: 미세 생활 기스 (실속형)  
**가성비**: 기능 정상, 외관 기스 있음  
**진열상품**: 전시 모델, 배터리 상태 최상"""
            st.session_state.is_in_consult = False
            final_df = None

        # B. 제품 추천 상담 (가이드 노출 없음)
        elif any(kw in q_clean for kw in (laptop_kw + phone_kw + pad_kw + watch_kw + context_kw)):
            st.session_state.is_in_consult = True
            with st.spinner("장부 확인 중..."):
                if any(kw in q_clean for kw in watch_kw): current_cat = "워치"
                elif any(kw in q_clean for kw in pad_kw): current_cat = "아이패드"
                elif any(kw in q_clean for kw in laptop_kw): current_cat = "맥북"
                elif any(kw in q_clean for kw in phone_kw): current_cat = "아이폰"
                else: current_cat = st.session_state.last_category
                
                full_cat_df = df[df['카테고리'].str.contains(current_cat, na=False)].sort_values(by='판매가')
                st.session_state.last_category = current_cat
                stock_result = full_cat_df.head(3)
                stock_list = stock_result.to_dict('records')

                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                sys_prompt = f"""너는 보상나라의 베테랑 점장이야. 
                
                [상담 지침]
                1. 원픽 & 논리적 상향판매: 손님의 용도에 현재 모델이 부족하면, 재고 리스트({stock_list}) 내의 고사양 모델을 '왜' 더 나은지 사양을 비교하며 제안해.
                2. 모순 금지: 문장 간에 앞뒤가 안 맞는 말을 하지 마. (예: 16G가 충분하다면서 갑자기 32G가 필요하다는 식의 모순)
                3. 데이터 무결성: [실제 재고 데이터]에 없는 모델이나 사양을 절대 지어내지 마. (환각 금지)
                4. 용어 박멸: '카테고리:', '권장용도:' 등 DB 필드명 노출 절대 금지.
                5. 가독성: 큰 제목(#) 사용 금지. 굵게(**)와 줄바꿈을 활용해 점장 말투로 써.
                6. 문맥 유지: 이전 대화 내용을 기억해서 대답해."""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                    temperature=0.0 
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기']].reset_index(drop=True)
                
        # C. 질문을 못 알아들었을 때 (가이드 노출)
        else:
            response = f"죄송합니다, 손님! 질문을 정확히 이해하지 못했어요. 아래 예시처럼 말씀해주시면 장부에서 바로 찾아드릴게요!  \n{guide_text}"
            st.session_state.is_in_consult = False
            final_df = None

        st.markdown(response)
        if final_df is not None:
            with st.expander("📊 추천 모델 상세 사양 확인하기", expanded=True):
                st.table(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response, "df": None})
