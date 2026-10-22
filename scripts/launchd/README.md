# Weekly home-IP scrape (mot, taipei_fukuoka, jposa_ja)

These three sources block GitHub Actions IPs (#378). `scraper/main.py` skips them in the CI daily run
(`HOME_IP_ONLY_SOURCES`) and they run once a week from a home IP instead.

The Mac must be on and online; launchd runs a missed Monday job when the Mac wakes. The script uses the
main checkout's `scraper/.env` and `.venv`, and fast-forwards that checkout to `origin/main` only when it
is clean and on `main`.

## Install (user runs these; they write outside the repo)

```bash
REPO="$HOME/Development/3-TTR/Tokyo Taiwan Radar"
sed -e "s|__REPO__|$REPO|g" -e "s|__USER__|$USER|g" "$REPO/scripts/launchd/com.ttr.home-ip-scrape.plist" \
  > ~/Library/LaunchAgents/com.ttr.home-ip-scrape.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.ttr.home-ip-scrape.plist
```

Run it once now to check: `launchctl kickstart -k "gui/$(id -u)/com.ttr.home-ip-scrape"`, then
`tail -f ~/Library/Logs/ttr-home-ip-scrape.log`.

## Remove

```bash
launchctl bootout "gui/$(id -u)/com.ttr.home-ip-scrape"
rm ~/Library/LaunchAgents/com.ttr.home-ip-scrape.plist
```
