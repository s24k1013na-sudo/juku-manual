import streamlit as st
import google.generativeai as genai  # 安定版のライブラリに変更
from supabase import create_client, Client

# --- セキュリティ設定（合言葉） ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("塾の合言葉を入力してください", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("合言葉が違います。もう一度入力してください", type="password", on_change=lambda: st.session_state.update({"password_correct": st.session_state["password"] == st.secrets["APP_PASSWORD"]}), key="password")
        st.error("😕 パスワードが正しくありません")
        return False
    return True

if not check_password():
    st.stop()

# --- 各種クライアントの初期化 ---
try:
    # 安定版の初期化方法
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"初期化エラー: {e}")
    st.stop()

# --- タブ切り替え ---
tab1, tab2 = st.tabs(["💬 AIチャット", "📝 マニュアル追加・一覧"])

with tab1:
    st.title("🤖 塾バイト・マニュアルAI")
    
    # DBからマニュアル取得
    try:
        response = supabase.table("manual").select("*").execute()
        db_data = response.data
        manual_items = [f"・{item['keyword']}: {item['content']}" for item in db_data]
        MANUAL_TEXT = "\n".join(manual_items) if manual_items else "現在マニュアルは登録されていません。"
    except Exception as e:
        st.error(f"DB連携エラー: {e}")
        MANUAL_TEXT = ""

    # システム命令（先輩としての振る舞い）
    SYSTEM_INSTRUCTION = f"あなたは塾の先輩です。以下のマニュアルに基づき回答してください。\n\n{MANUAL_TEXT}"

    # セッション履歴の初期化（Gemini標準の形式に合わせる）
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # チャット表示用のメッセージ履歴（Streamlit表示用）
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です！何か分からないことがあれば聞いてくださいね。"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 入力フォーム
    if user_input := st.chat_input("質問を入力..."):
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            try:
                # 安定版のモデル呼び出し
                model = genai.GenerativeModel(
                    model_name='gemini-1.5-flash',
                    system_instruction=SYSTEM_INSTRUCTION
                )
                
                # 会話の開始
                chat = model.start_chat(history=st.session_state.chat_history)
                
                # ストリーミング応答
                res = chat.send_message(user_input, stream=True)
                
                for chunk in res:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                
                # 履歴を保存（Gemini用と表示用両方）
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.chat_history.append({"role": "user", "parts": [user_input]})
                st.session_state.chat_history.append({"role": "model", "parts": [full_response]})

            except Exception as e:
                st.error(f"AI応答エラーが発生しました: {e}")

with tab2:
    st.header("📝 マニュアルの追加")
    with st.form("add_form", clear_on_submit=True):
        new_keyword = st.text_input("キーワード")
        new_content = st.text_area("説明文")
        if st.form_submit_button("登録"):
            if new_keyword and new_content:
                supabase.table("manual").insert({"keyword": new_keyword, "content": new_content}).execute()
                st.success("登録完了！")
                st.rerun()