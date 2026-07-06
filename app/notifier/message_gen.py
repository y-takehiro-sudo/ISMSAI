"""OpenAI APIを使ってGoogle Chat向けメッセージ本文を生成する。"""
import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 通知種別 → 日本語ラベル
_TYPE_LABELS = {
    "start":          "開始通知",
    "midpoint":       "中間リマインド",
    "week_before":    "期限7日前",
    "pre_deadline":   "前日リマインド",
    "deadline":       "期限日",
    "overdue":        "期限超過（未完了）",
    "daily_reminder": "回答リマインド",
}


def generate_message(
    task_name: str,
    task_description: str,
    assignee_name: str,
    due_date: str,
    notify_type: str,
    report_url: Optional[str] = None,
) -> str:
    """
    OpenAI APIでGoogle Chat通知メッセージを生成する。
    API失敗時はテンプレート文字列にフォールバックする。
    """
    try:
        return _generate_with_openai(
            task_name, task_description, assignee_name, due_date, notify_type, report_url
        )
    except Exception as e:
        logger.error(f"OpenAI APIメッセージ生成失敗、テンプレートにフォールバック: {e}")
        return _fallback_message(task_name, due_date, notify_type, report_url)


def _generate_with_openai(
    task_name: str,
    task_description: str,
    assignee_name: str,
    due_date: str,
    notify_type: str,
    report_url: Optional[str],
) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY が .env に設定されていません")

    client = OpenAI(api_key=api_key)
    type_label = _TYPE_LABELS.get(notify_type, notify_type)
    report_line = f"\n完了報告URL: {report_url}" if report_url else ""

    prompt = f"""あなたはISMS運用管理システムのアシスタントです。
以下の情報をもとに、Google Chatに投稿する簡潔で丁寧な日本語メッセージを作成してください。

タスク名: {task_name}
作業内容: {task_description or "（詳細なし）"}
期限: {due_date}
通知種別: {type_label}
{report_line}

要件:
- 150文字以内
- 丁寧だが簡潔に（ビジネスチャット向け）
- 担当者名は含めない（メンションで別途行うため）
- 完了報告URLがある場合は必ず含める
- 絵文字は1〜2個まで
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        max_tokens=300,
        messages=[
            {"role": "system", "content": "あなたはISMS運用管理の通知メッセージ生成AIです。"},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _fallback_message(
    task_name: str,
    due_date: str,
    notify_type: str,
    report_url: Optional[str],
) -> str:
    """OpenAI API未設定・失敗時のテンプレートメッセージ"""
    url_line = f"\n✅ 完了報告: {report_url}" if report_url else ""

    templates = {
        "start":          f"【ISMS】「{task_name}」の実施期間が始まりました。期限: {due_date}{url_line}",
        "midpoint":       f"【中間リマインド】「{task_name}」の進捗を確認してください。期限: {due_date}{url_line}",
        "week_before":    f"【7日前】「{task_name}」の期限が1週間後に迫っています。期限: {due_date}{url_line}",
        "pre_deadline":   f"【前日】「{task_name}」の期限は明日です。期限: {due_date}{url_line}",
        "deadline":       f"【期限日】「{task_name}」の対応期限は本日です。{url_line}",
        "overdue":        f"【期限超過】「{task_name}」が未完了です。早急に対応をお願いします。期限: {due_date}{url_line}",
        "daily_reminder": f"【回答リマインド】「{task_name}」への回答がまだ届いていません。期限: {due_date}{url_line}",
    }
    return templates.get(notify_type, f"【ISMS】「{task_name}」の対応をお願いします。期限: {due_date}{url_line}")
