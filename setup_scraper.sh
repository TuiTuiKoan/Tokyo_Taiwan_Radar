#!/bin/bash
# setup_scraper.sh — 一鍵安裝爬蟲所需的 Python 套件
# 執行方式：在終端機中 cd 到專案根目錄，然後 bash setup_scraper.sh

set -e

echo "🔍 確認 Python 版本..."
python3 --version

echo ""
echo "📦 在現有的 venv 中安裝套件..."
source venv/bin/activate

pip install -r scraper/requirements.txt

echo ""
echo "🎭 安裝 Playwright Chromium 瀏覽器..."
playwright install chromium

echo ""
echo "✅ 完成！接下來請："
echo "   1. 複製 scraper/.env.example → scraper/.env"
echo "   2. 填入 SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY、DEEPL_API_KEY"
echo "   3. 執行：source venv/bin/activate && python scraper/main.py"
