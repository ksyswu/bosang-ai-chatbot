import streamlit as st
import pandas as pd
from groq import Groq

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(page_title="보상나라 AI 점장님", layout="wide")
st.title("💻 보상나라 AI 점장님 실시간 상담")

# --- 2. 데이터 로드 함수 (캐싱 적용) ---
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

# --- 3. 세션 상태 관리 (대화 문맥 및 플래그) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_category" not in st.session_state:
    st.session_state.last_category = "아이폰"
if "waiting_for_purpose" not in st.session_state:
    st.session_state.waiting_for_purpose = False

# --- 4. 사이드바 등급 가이드 ---
with st.sidebar:
    st.header("✨ 보상나라 등급 기준")
    st.markdown("""
    - **S 등급**: 신품급! 선물용 강추! 🎁  
    - **A 등급**: 깔끔함. 미세 흔적, 가성비 최고 ✨  
    - **B 등급**: 생활 기스 있음. 기능은 완벽 💯  
    - **가성비**: 찍힘 등 외관 흔적 있음 (실속파) 💪  
    - **진열상품**: 매장 전시용. 배터리 효율 최상 🚀  
    """)

# --- 5. 이전 대화 렌더링 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg: st.dataframe(msg["df"])

# --- 6. 메인 상담 로직 ---
if user_input := st.chat_input("질문을 입력하세요! (예: 가볍게 쓸 세컨폰 추천해줘)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)

    with st.chat_message("assistant"):
        q_clean = user_input.replace(" ", "")
        
        # [키워드 분류]
        watch_kw = ["워치", "시계", "수영", "운동", "런닝", "심박수", "애플워치"]
        phone_kw = ["폰", "아이폰", "핸드폰", "스마트폰", "세컨", "서브"]
        mac_kw = ["맥북", "노트북", "랩탑", "코딩", "작업"]
        pad_kw = ["패드", "아이패드", "태블릿", "필기", "드로잉"]
        trade_kw = ["추천", "가성비", "가격", "시세", "있어", "매물", "재고", "얼마", "사고", "구매", "저렴", "싼", "최저가"]
        grade_kw = ["등급", "S급", "A급", "B급", "상태", "기준"]
        
        # [용도 파악 플래그]
        purpose_kw = ["용도", "유튜브", "게임", "작업", "인강", "일상", "촬영", "세컨", "서브", "운동", "필기", "공부"]
        user_already_stated_purpose = any(kw in user_input for kw in purpose_kw)

        # 의도 분류
        is_grade_only = any(kw in q_clean for kw in grade_kw) and not any(kw in user_input for kw in trade_kw)
        is_recommend_talk = any(kw in user_input for kw in (trade_kw + watch_kw + phone_kw + mac_kw + pad_kw))
        is_reply = st.session_state.waiting_for_purpose and len(q_clean) >= 2

        response = ""
        final_df = None

        # [CASE 1] 등급 문의 (단순 정보 제공)
        if is_grade_only:
            response = """보상나라 등급 기준은 이렇습니다! 😊  
            * **S 등급**: 신품급! 🎁  
            * **A 등급**: 미세 흔적, 가성비 최고 ✨  
            * **B 등급**: 생활 기스, 기능 완벽 💯  
            
            지금 바로 추천이 필요하신 모델이 있나요?"""
            st.session_state.waiting_for_purpose = False

        # [CASE 2] 추천/재고/가격/용도 답변 (메인 영업 로직)
        elif is_recommend_talk or is_reply:
            with st.spinner("장부를 확인 중입니다..."):
                # 카테고리 업데이트
                if any(kw in user_input for kw in watch_kw): st.session_state.last_category = "애플워치"
                elif any(kw in user_input for kw in phone_kw): st.session_state.last_category = "아이폰"
                elif any(kw in user_input for kw in mac_kw): st.session_state.last_category = "맥북"
                elif any(kw in user_input for kw in pad_kw): st.session_state.last_category = "아이패드"
                
                cat_df = df[df['카테고리'].str.contains(st.session_state.last_category, na=False)].copy()
                
                # 정렬 및 필터링
                if any(kw in user_input for kw in ["저렴", "싼", "최저가"]):
                    cat_df = cat_df.sort_values(by='판매가', ascending=True)
                
                search_word = user_input.split()[0] if not is_reply else ""
                target_stock = cat_df[cat_df['상품명 (정제형)'].str.contains(search_word, case=False, na=False)] if search_word else pd.DataFrame()
                
                stock_result = target_stock.head(3) if not target_stock.empty else cat_df.head(3)
                stock_list = stock_result.to_dict('records')
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                # [강화된 전문가 프롬프트]
                sys_prompt = f"""너는 '보상나라'의 베테랑 점장이야. 
                [영업 지침]
                1. 한 답변 안에서 같은 형용사(예: 적합하다, 가볍다)를 3번 이상 반복하지 마. 문장을 다채롭게 써라.
                2. 사용자가 "{user_input}"라고 말한 의도를 정확히 파악해서 첫 문장에 공감해줘. (예: 세컨폰이면 휴대성이 제일 중요하죠!)
                3. 재고의 특징을 나열하지 말고, 그 특징이 고객에게 왜 좋은지 '전문가적 조언'을 섞어줘.
                4. 다른 브랜드(삼성 등) 추천 절대 금지. 한자 사용 금지. 
                5. 답변 끝에 반드시 공백 2개('  ')를 넣어 줄바꿈을 지켜라.
                
                [재고]: {stock_list}"""

                res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "system", "content": sys_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]],
                    temperature=0.5 # 자연스러운 말투를 위해 살짝 올림
                ).choices[0].message.content
                
                response = res.replace("\n", "  \n")
                final_df = stock_result[['상품명 (정제형)', '등급', '판매가_표기', '배터리_표기', '권장용도']]
                
                # [중요] 눈치 챙기기: 이미 용도를 말했다면 다시 묻지 않음
                if not user_already_stated_purpose and not is_reply:
                    response += "  \n\n**고객님, 어떤 용도로 쓰실 예정인가요? 말씀해 주시면 딱 맞는 모델을 더 정밀하게 추천해 드릴 수 있습니다!**"
                    st.session_state.waiting_for_purpose = True
                else:
                    st.session_state.waiting_for_purpose = False

        # [CASE 3] 답변 불가 (가이드 메뉴)
        if not response:
            response = """어이쿠, 고객님! 그 부분은 제가 답변 드리기 어렵네요 😅  
용도에 맞는 제품 추천이나 등급 기준에 대해 물어봐주시면 점장님이 정성을 다해 대답해 드릴게요!  

**💡 이렇게 물어보시면 점장님이 잘 대답해드려요!**
1. "사진 잘 나오는 **아이폰** 추천해줘" 📸
2. "인강용 가성비 **맥북** 있어?" 💻
3. "운동할 때 쓸 **애플워치** 추천해줘" ⌚
4. "보상나라 **등급 기준**이 뭐야?" 📋"""

        # 최종 결과 출력
        st.markdown(response)
        if final_df is not None:
            with st.expander("📦 추천 상품 목록 확인하기"):
                st.dataframe(final_df)
            st.session_state.messages.append({"role": "assistant", "content": response, "df": final_df})
        else:
            st.session_state.messages.append({"role": "assistant", "content": response})
