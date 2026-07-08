#!/usr/bin/env bash
# 最小 smoke 测试：各 dataset 非流式导入 + sync-status
# 用法: ./scripts/smoke_import.sh [BASE_URL]
# 默认 BASE_URL=http://localhost:8000

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
API="${BASE_URL}/api/v1"

check_code() {
  local label="$1"
  local body="$2"
  local code
  code=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('code', -1))")
  if [ "$code" != "0" ]; then
    echo "FAIL [$label] code=$code"
    echo "$body"
    exit 1
  fi
  echo "OK   [$label]"
}

echo "=== smoke import @ ${API} ==="

for dataset in turnover point global_assets; do
  body=$(curl -sf -X POST "${API}/admin/data/import?dataset=${dataset}")
  check_code "import/${dataset}" "$body"
done

body=$(curl -sf "${API}/admin/data/sync-status")
check_code "sync-status" "$body"

echo "=== all passed ==="
