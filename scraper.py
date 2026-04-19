from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()

        print("機器人出發！前往活動內頁...")
        # ⚠️ 請替換成真實的網址
        page.goto("https://jp.taiwan.culture.tw/你要替換的活動內頁網址")
        page.wait_for_load_state("networkidle")

        print("\n啟動「智能錄影機」模式...\n")
        
        all_paragraphs = page.locator("p").all_inner_texts()
        
        exhibition_content = []
        speakers_content = []
        
        # 這次我們只用一個變數來控制狀態："exhibition" 或 "speakers" 或 None (關閉)
        recording_mode = None

        for line in all_paragraphs:
            clean_line = line.replace("\xa0", "").strip()
            
            if clean_line == "":
                continue

            # --- 判斷要不要切換頻道 ---
            
            # 只要句子裡包含這個關鍵字就觸發 (不管前面是 ■ 還是 【)
            if "展示・体験内容" in clean_line:
                recording_mode = "exhibition"
                continue # 跳過標題這行
                
            elif "登壇者紹介" in clean_line:
                recording_mode = "speakers"
                continue # 跳過標題這行
                
            # 當遇到【イベント】時，代表展示內容結束了，關閉錄影機
            elif "【イベント】" in clean_line:
                recording_mode = None
                continue

            # --- 開始錄影 ---
            
            if recording_mode == "exhibition":
                exhibition_content.append(clean_line)
                
            elif recording_mode == "speakers":
                speakers_content.append(clean_line)

        final_exhibition_text = "\n".join(exhibition_content)
        final_speakers_text = "\n".join(speakers_content)

        print("🎉 成功抓取大段落！")
        print("=========================================")
        print("📍 【展示・体験内容】:\n")
        print(final_exhibition_text)
        print("\n-----------------------------------------")
        print("📍 【登壇者紹介】:\n")
        print(final_speakers_text)
        print("=========================================")

        browser.close()

if __name__ == "__main__":
    run()