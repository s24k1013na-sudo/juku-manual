import streamlit as st
from google import genai
from google.genai import types
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
    # api_key を明示的に指定
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
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
    
    # マニュアルデータの取得
    try:
        response = supabase.table("manual").select("*").execute()
        db_data = response.data
        manual_items = [f"・{item['keyword']}: {item['content']}" for item in db_data]
        MANUAL_TEXT = "\n".join(manual_items) if manual_items else "現在マニュアルは登録されていません。"
    except Exception as e:
        st.error(f"DB連携エラー: {e}")
        MANUAL_TEXT = "マニュアルの取得に失敗しました。"

    # システムインストラクションの設定
    SYSTEM_INSTRUCTION = f"あなたは塾の先輩です。以下のマニュアルに基づき、後輩の講師に親身に回答してください。\n\n【塾のマニュアル】\n{MANUAL_TEXT}"

    # チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "お疲れ様です！何か分からないことがあれば聞いてくださいね。"}]

    # 履歴の表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ユーザー入力
    if user_input := st.chat_input("質問を入力..."):
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            try:
                # モデルを安定版の 'gemini-1.5-flash' に変更
                # これにより 429 RESOURCE_EXHAUSTED エラーを回避しやすくします
                res = client.models.generate_content_stream(
                    model='gemini-1.5-flash', 
                    contents=user_input,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.7,
                    )
                )
                
                for chunk in res:
                    if chunk.text:
                        full_response += chunk.text
                        response_placeholder.write(full_response + "▌")
                response_placeholder.write(full_response)
                
                # 応答を履歴に追加
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                # エラーメッセージを分かりやすく表示
                if "429" in str(e):
                    error_msg = "⚠️ AIの無料枠制限（1分間の回数制限）に達しました。20〜30秒待ってから再度入力してください。"
                else:
                    error_msg = f"AI応答エラーが発生しました: {e}"
                
                st.error(error_msg)
                # エラー時は履歴に追加しない（またはエラーメッセージを追加する）

with tab2:
    st.header("📝 マニュアルの管理")
    
    # 追加フォーム
    with st.form("add_form", clear_on_submit=True):
        st.subheader("新規追加")
        new_keyword = st.text_input("キーワード（例：遅刻連絡、コピー機の使い方）")
        new_content = st.text_area("説明文")
        if st.form_submit_button("登録"):
            if new_keyword and new_content:
                try:
                    supabase.table("manual").insert({"keyword": new_keyword, "content": new_content}).execute()
                    st.success("マニュアルを登録しました！")
                    st.rerun()
                except Exception as e:
                    st.error(f"登録失敗: {e}")
            else:
                st.warning("キーワードと説明文の両方を入力してください。")

    # 一覧表示（簡易版）
    if st.checkbox("登録済みマニュアルを表示"):
        try:
            response = supabase.table("manual").select("*").execute()
            for item in response.data:
                with st.expander(f"📌 {item['keyword']}"):
                    st.write(item['content'])
        except Exception as e:
            st.error(f"一覧取得エラー: {e}")