#!/bin/sh
set -e

# 初回のみ：管理者ユーザーが存在しない場合に初期作成
python scripts/bootstrap_admin.py

# アプリ起動
exec "$@"
