# -*- coding: utf-8 -*-
"""OpenAI API + Google Chat Webhook 接続テストスクリプト
使い方: python test_ai_connection.py
"""
import os
import sys

# Windows コンソール文字化け対策
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()


def test_openai():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("[FAIL] OPENAI_API_KEY が .env に設定されていません")
        return False

    print(f"[OK] OPENAI_API_KEY 確認 (先頭8文字: {api_key[:8]}...)")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        print("[...] OpenAI API に接続中...")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=100,
            messages=[
                {"role": "user", "content": "「ISMSタスク確認」の開始通知を1文で作ってください。"}
            ],
        )
        message = response.choices[0].message.content.strip()
        print(f"[OK] API接続成功！")
        print(f"     生成メッセージ例: {message}")
        return True

    except Exception as e:
        print(f"[FAIL] API接続失敗: {e}")
        return False


def test_webhook():
    url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")
    if not url:
        print("\n[SKIP] GOOGLE_CHAT_WEBHOOK_URL が未設定のため Google Chat テストをスキップ")
        print("       .env に GOOGLE_CHAT_WEBHOOK_URL=https://... を設定してください")
        return

    import httpx
    print(f"\n[...] Google Chat Webhook に接続中...")
    try:
        resp = httpx.post(url, json={"text": "【ISMSテスト】Webhook接続確認メッセージです。"}, timeout=10)
        if resp.status_code == 200:
            print("[OK] Google Chat Webhook 送信成功！スペースを確認してください。")
        else:
            print(f"[FAIL] 送信失敗 HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[FAIL] 接続例外: {e}")


def test_message_gen():
    from app.notifier.message_gen import generate_message
    print("\n[...] message_gen モジュール テスト中...")
    msg = generate_message(
        task_name="セキュリティパッチ適用",
        task_description="全サーバーに最新パッチを適用する",
        assignee_name="田中太郎",
        due_date="2026-06-30",
        notify_type="week_before",
    )
    print(f"[OK] メッセージ生成成功:")
    print(f"     {msg}")


if __name__ == "__main__":
    print("=" * 50)
    print("ISMS 外部接続テスト")
    print("=" * 50)
    ok = test_openai()
    if ok:
        test_message_gen()
    test_webhook()
    print("=" * 50)
