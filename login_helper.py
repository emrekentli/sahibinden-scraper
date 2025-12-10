#!/usr/bin/env python3
"""
Sahibinden.com Login Helper
Bu script ile manuel login yapıp cookies'leri kaydedebilirsiniz.
Kaydedilen cookies sonra scraper tarafından kullanılacak.
"""

import undetected_chromedriver as uc
import json
import time
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("=" * 60)
    print("Sahibinden.com Login Helper")
    print("=" * 60)
    print("\nBu script ile Sahibinden.com'a manuel login yapacaksınız.")
    print("OTP kodunu girdikten sonra cookies kaydedilecek.\n")

    # Chrome'u başlat
    logging.info("Chrome başlatılıyor...")
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')

    # Biraz daha insansı görünmek için (zorunlu değil ama iyi olur)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')

    # İstersen aynı profili kullanmak için bunu açabilirsin:
    # options.add_argument(r'--user-data-dir=/tmp/sahibinden-profile')

    # Buradaki kritik kısım: Chrome 143 kullanıyorsun
    driver = uc.Chrome(
     options=options,
     headless=False,
     version_main=142
    )


    try:
        # Sahibinden.com login sayfasına git
        logging.info("Login sayfası açılıyor...")
        driver.get('https://secure.sahibinden.com/login')
        time.sleep(3)

        print("\n" + "=" * 60)
        print("LÜTFEN BROWSER'DA LOGIN OLUN:")
        print("=" * 60)
        print("1. Email/kullanıcı adınızı girin")
        print("2. Şifrenizi girin")
        print("3. OTP kodunu girin")
        print("4. Ana sayfaya yönlendirilene kadar bekleyin")
        print("\nLogin tamamlandıktan sonra bu terminalde ENTER'a basın...")
        print("=" * 60)

        input("\nLogin tamamlandıysa ENTER'a basın: ")

        # URL kontrolü
        current_url = driver.current_url
        if 'login' in current_url.lower():
            print("\n❌ HATA: Hala login sayfasındasınız!")
            print("Lütfen login'i tamamlayın ve tekrar deneyin.")
            return

        # Cookies'leri kaydet
        cookies = driver.get_cookies()

        # Data klasörü varsa oraya kaydet, yoksa current directory'e
        data_dir = '/app/data' if os.path.exists('/app/data') else '.'
        cookies_file = os.path.join(data_dir, 'sahibinden_cookies.json')

        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Cookies başarıyla kaydedildi: {cookies_file}")
        print(f"   Toplam {len(cookies)} cookie kaydedildi")
        print("\nBu cookies scraper tarafından otomatik olarak kullanılacak.")
        print("Cookies expire olana kadar tekrar login yapmanıza gerek yok.\n")

    except Exception as e:
        print(f"\n❌ HATA: {e}")
    finally:
        logging.info("Browser kapatılıyor...")
        driver.quit()
        print("\nTamamlandı!")

if __name__ == "__main__":
    main()
