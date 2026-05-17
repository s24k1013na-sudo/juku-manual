import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client

# --- 1. セキュリティ設定（合言葉） ---
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

# --- 2. 各種クライアントの初期化 ---
try:
    # 安定版 SDK の設定
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # Supabase 設定
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"初期化エラー（Secretsの設定を確認してください）: {e}")
    st.stop()

# --- 3. タブ切り替え ---
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
        MANUAL_TEXT = "マニュアルが読み込めませんでした。"

    # システム命令（AIのキャラクター設定）
    SYSTEM_INSTRUCTION = f"あなたは塾の先輩講師です。以下の【塾のマニュアル】の内容に基づき、後輩に教えるように親身に回答してください。マニュアルにないことは「担当者に確認してください」と伝えてください。\n\n【塾のマニュアル】\n{MANUAL_TEXT}"

    # セッション履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です！何か分からないことがあれば聞いてくださいね。"}]
    
    # Gemini用の会話履歴（内部保持用）
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 画面上のチャット履歴表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ユーザー入力
    if user_input := st.chat_input("質問を入力..."):
        # ユーザー入力を画面に表示＆保存
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            try:
                # モデルの準備（404対策のため 'models/' プレフィックスを付与）
                model = genai.GenerativeModel(
                    model_name='models/gemini-1.5-flash',
                    system_instruction=SYSTEM_INSTRUCTION
                )
                
                # 会話開始（過去の履歴を渡す）
                chat = model.start_chat(history=st.session_state.chat_history)
                
                # ストリーミング応答の実行
                res = chat.send_message(user_input, stream=True)
                
                for chunk in res:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                
                # 履歴の保存（表示用とAI用）
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.chat_history.append({"role": "user", "parts": [user_input]})
                st.session_state.chat_history.append({"role": "model", "parts": [full_response]})

            except Exception as e:
                if "429" in str(e):
                    st.error("⚠️ AIの無料枠制限に達しました。30秒ほど待ってからもう一度入力してください。")
                else:
                    st.error(f"AI応答エラーが発生しました: {e}")

with tab2:
    st.header("📝 マニュアルの管理")
    
    # 追加フォーム
    with st.form("add_form", clear_on_submit=True):
        new_keyword = st.text_input("キーワード（例：コピー機、欠勤連絡）")
        new_content = st.text_area("説明文")
        if st.form_submit_button("登録"):
            if new_keyword and new_content:
                try:
                    supabase.table("manual").insert({"keyword": new_keyword, "content": new_content}).execute()
                    st.success("マニュアルを登録しました！")
                    st.rerun()
                except Exception as e:
                    st.error(f"登録エラー: {e}")
            else:
                st.warning("キーワードと説明文を入力してください。")

    # 一覧表示
    if st.checkbox("登録済みマニュアルを一覧表示"):
        try:
            res = supabase.table("manual").select("*").execute()
            for item in res.data:
                with st.expander(f"📌 {item['keyword']}"):
                    st.write(item['content'])
        except Exception as e:
            st.error(f"読み込みエラー: {e}")