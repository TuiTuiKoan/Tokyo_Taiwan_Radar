from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()

        print("機器人出發！直接前往活動內頁...")
        # ⚠️ 請將下面的網址替換成你剛剛 inspect 的那個活動頁面的完整網址！
        page.goto("https://jp.taiwan.culture.tw/News_Content2.aspx?n=365&s=253351")

        print("等待網頁資料載入中...")
        page.wait_for_load_state("networkidle")

        print("\n開始啟動「關鍵字掃描」模式...")
        
        # 1. 抓取地點 (尋找包含「会場：」的 p 標籤)
        location_element = page.locator("p").filter(has_text="会場：")
        # 確保有找到東西才印出來
        if location_element.count() > 0:
            # .first 是因為可能有時候網頁會重複寫，我們取第一個就好
            print(f"📍 成功抓取地點: {location_element.first.inner_text()}")

        # 2. 抓取時間 (尋找包含「時間：」的 p 標籤)
        time_element = page.locator("p").filter(has_text="時間：")
        if time_element.count() > 0:
            print(f"⏰ 成功抓取時間: {time_element.first.inner_text()}")

        # 3. 抓取費用 (尋找包含「入場：」的 p 標籤)
        price_element = page.locator("p").filter(has_text="入場：")
        if price_element.count() > 0:
            print(f"💰 成功抓取費用: {price_element.first.inner_text()}")

        print("=========================================")

        # 暫停 3 秒讓我們看結果，然後關閉
        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()