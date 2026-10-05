import asyncio
import pandas as pd
import re
from playwright.async_api import async_playwright

def clean_text(text):
    if not text:
        return ""
    # Menghapus karakter newline/enter agar CSV tidak berantakan
    text = re.sub(r'[\r\n]+', ' ', text)
    # Menghapus spasi ganda
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

async def scrape_tiktok_comments(url, target_comments=1100):
    async with async_playwright() as p:
        # Membuka browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        print(f"Membuka URL: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        # Buka panel komentar jika belum terbuka
        try:
            comment_btn = await page.wait_for_selector('[data-e2e="comment-icon"], [data-e2e="comment-count"]', timeout=4000)
            if comment_btn:
                await comment_btn.click()
                print("Menekan tombol komentar...")
                await page.wait_for_timeout(2000)
        except Exception:
            print("Panel komentar sudah terbuka atau tombol tidak ditemukan.")

        comments_data = []
        seen_keys = set()
        no_new_data_count = 0
        
        print(f"Mulai mengambil komentar (Target: {target_comments} data)...")

        while len(comments_data) < target_comments:
            # Ambil semua blok komentar (utama maupun balasan)
            comment_elements = await page.query_selector_all('[class*="DivCommentObjectWrapper"]')
            
            initial_count = len(comments_data)

            for el in comment_elements:
                try:
                    # 1. Nama Akun
                    username_el = await el.query_selector('[data-e2e="comment-username-1"], [class*="DivUsernameContentWrapper"], [class*="UsernameContentWrapper"]')
                    username = clean_text(await username_el.inner_text()) if username_el else ""

                    # 2. Isi Komentar
                    text_el = await el.query_selector('[class*="span-comment-level-1"], [class*="DivCommentContentWrapper"], [class*="PCommentText"]')
                    comment_text = clean_text(await text_el.inner_text()) if text_el else ""

                    # 3. Tanggal / Waktu Komentar
                    time_el = await el.query_selector('[class*="DivCommentSubContentSplitWrapper"] span, [class*="SpanTime"]')
                    comment_time = clean_text(await time_el.inner_text()) if time_el else ""

                    # 4. Tipe Komentar (Utama / Balasan)
                    # Cek class parent atau class elemen untuk membedakan balasan
                    el_class = await el.get_attribute("class") or ""
                    type_komen = "Balasan" if "Reply" in el_class or "Sub" in el_class else "Utama"

                    # Kunci unik untuk menghindari duplikasi data
                    unique_key = f"{username}_{comment_text}_{comment_time}"

                    if username and comment_text and unique_key not in seen_keys:
                        seen_keys.add(unique_key)
                        comments_data.append({
                            'nama_akun': username,
                            'komen': comment_text,
                            'tanggal_komen': comment_time,
                            'type_komen': type_komen
                        })

                        if len(comments_data) >= target_comments:
                            break
                except Exception:
                    continue

            print(f"Terkumpul: {len(comments_data)} / {target_comments} komentar")

            # Jika target sudah tercapai, keluar loop
            if len(comments_data) >= target_comments:
                break

            # Cek apakah ada data baru dalam iterasi ini
            if len(comments_data) == initial_count:
                no_new_data_count += 1
                if no_new_data_count >= 15:
                    print("Tidak ada komentar baru lagi yang dapat dimuat. Proses dihentikan.")
                    break
            else:
                no_new_data_count = 0

            # Auto Scroll wadah/panel komentar
            side_panel = await page.query_selector('[class*="DivCommentListContainer"], [class*="DivCommentMain"]')
            if side_panel:
                await side_panel.evaluate("node => node.scrollTop += 1200")
            else:
                await page.evaluate("window.scrollBy(0, 1200)")
                
            await page.wait_for_timeout(1500)

        await browser.close()
        return comments_data

tiktok_url = "https://www.tiktok.com/@officialinews/video/7690537011848940820?is_from_webapp=1&sender_device=pc&web_id=7645379394748188168"

if __name__ == "__main__":
    data = asyncio.run(scrape_tiktok_comments(tiktok_url, target_comments=1100))
    
    # Simpan ke CSV dengan pemisah koma resmi
    df = pd.DataFrame(data)
    df.to_csv("tiktok_comments.csv", index=False, encoding="utf-8-sig")
    print(f"\nSelesai! Berhasil mengambil {len(df)} komentar dan menyimpan ke 'tiktok_comments.csv'")