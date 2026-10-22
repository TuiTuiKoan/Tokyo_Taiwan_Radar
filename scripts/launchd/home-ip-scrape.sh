#!/bin/bash
# Weekly scrape of the sources that block GitHub Actions IPs (#378): mot, taipei_fukuoka, jposa_ja.
# Run by launchd (com.ttr.home-ip-scrape.plist) from the main checkout, which holds scraper/.env.
# Never prints secrets; output goes to ~/Library/Logs/ttr-home-ip-scrape.log.
set -u

REPO="${TTR_REPO:-$HOME/Development/3-TTR/Tokyo Taiwan Radar}"
PYTHON="${TTR_PYTHON:-$REPO/.venv/bin/python}"
SOURCES="mot,taipei_fukuoka,jposa_ja"

echo "=== $(date '+%F %T %Z') home-ip-scrape start ==="

[ -x "$PYTHON" ] || { echo "python not found: $PYTHON"; exit 1; }
[ -f "$REPO/scraper/.env" ] || { echo "scraper/.env missing in $REPO"; exit 1; }

cd "$REPO" || exit 1

# Use current main when the checkout is clean and fast-forwardable; otherwise run what is there.
if [ -z "$(git status --porcelain)" ] && [ "$(git branch --show-current)" = "main" ]; then
  git fetch -q origin && git merge --ff-only -q origin/main || echo "git update skipped (not fast-forwardable)"
else
  echo "git update skipped (checkout is not clean main)"
fi

cd "$REPO/scraper" || exit 1
"$PYTHON" main.py --source "$SOURCES"
rc=$?
echo "=== $(date '+%F %T %Z') home-ip-scrape end rc=$rc ==="
exit $rc
