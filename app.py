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

# --- 3. 사이드바 안내 (등급표 상시 노출) ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# --- 4. 대화 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 5. 상담 엔진 (전문가 검수 완료) ---
if user_input := st.chat_input("질문을 입력하세요! (예: 수영할 때 쓸 워치 추천해줘)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [키워드 사전 보강]
        watch_kw = ["워치", "시계", "수영", "운동", "런닝", "심박수", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰", "셀카", "카메라", "전화"]
        mac_kw = ["맥북", "노트북", "랩탑", "코딩", "작업", "편집", "프로그래밍", "인강"]
        pad_kw = ["패드", "아이패드", "태블릿", "필기", "드로잉", "넷플릭스"]
        
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "저렴", "싼", "보여줘"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]

        # 카테고리 판별 및 업데이트
        if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
        elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
        elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
        elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"

        # 상담 가능 여부 판단
        is_trade_talk = any(kw in user_input for kw in trade_kw) or any(kw in user_input for kw in (watch_kw + phone_kw + mac_kw + pad_kw))
        is_grade_query = any(kw in q_clean for kw in grade_kw)
        
        response = ""
        final_df = None

        # [상황 A] 정상 상담 (재고 검색 및 큐레이션)
        if (is_trade_talk or is_grade_query) and len(q_clean) >= 2:
            if is_grade_query and not any(kw in user_input for kw in trade_kw):
                # 등급 기준만 물어본 경우
                response = """고객님! 보상나라의 등급 기준을 안내해 드립니다! 😊  
                (더 자세한 내용은 왼쪽 사이드바에서도 확인하실 수 있어요!)  
                
                * **S 등급**: 신품급! 선물용 강추! 🎁  
                * **A 등급**: 깔끔함. 미세 흔적 가성비 최고 ✨  
                * **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
                * **가성비**: 찍힘 등 외관 흔적 있음. 실속파 추천 💪"""
            else:
                # 상품 추천 로직
                with st.spinner("점장님이 장부를 확인 중입니다..."):
                    cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                    
                    # 상세 모델 필터링 (질문 키워드 기반)
                    stock_result = cat_df.head(3) # 기본값 상위 3개
                    stock_list = stock_result.to_dict('records')
                    
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    sys_prompt = f"""너는 '보상나라' 베테랑 점장이야. 
                    1. [재고] 리스트의 모델만 추천할 것. 
                    2. '💬 점장 추천' 항목에 고객의 질문("{user_input}")에 딱 맞는 이유를 전문가답게 작성해.
                    3. 문법적으로 완벽한 줄바꿈을 위해 문장 끝에 공백 2개를 넣어라.
                    
                    [재고]: {stock_list}"""

                    res = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "system", "content": sys_prompt}] + 
                                 [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-3:]],
                        temperature=0.4
                    ).choices[0].message.content
                    
                    response = res.replace("\n", "  \n")
                    final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]

        # [상황 B] 답변 불가 시 가이드 노출
        if not response:
            response = """어이쿠, 고객님! 제가 그 부분은 아직 답변이 어려워요 😅  
전자기기 추천이나 시세, 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!

---
**💡 이렇게 물어보시면 점장님이 잘 대답해드려요!**
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강/과제용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 궁금해!" 📋
---"""

        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
