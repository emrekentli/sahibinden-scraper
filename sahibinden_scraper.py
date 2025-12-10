import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import json
import logging
import schedule
from datetime import datetime
import os
from email_sender import EmailSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sahibinden_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class SahibindenScraper:
    def __init__(self, config_file='config.json'):
        self.driver = None
        self.config = self.load_config(config_file)
        self.max_replaced_parts = self.config.get('max_replaced_parts', 1)
        self.max_painted_parts = self.config.get('max_painted_parts', 2)
        self.filtered_listings = []
        # Docker volume'da saklamak için /app/data kullan, yoksa mevcut dizin
        self.data_dir = '/app/data' if os.path.exists('/app/data') else '.'
        self.seen_ads_file = os.path.join(self.data_dir, 'seen_ads.json')
        self.cookies_file = os.path.join(self.data_dir, 'sahibinden_cookies.json')
        self.status_file = os.path.join(self.data_dir, 'scraper_status.json')
        self.otp_file = os.path.join(self.data_dir, 'otp_code.json')
        self.seen_ads = self.load_seen_ads()
        self.email_sender = EmailSender()

    def load_config(self, config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return {
                'check_interval_minutes': 30,
                'max_replaced_parts': 1,
                'max_painted_parts': 2,
                'brands': []
            }

    def load_seen_ads(self):
        try:
            with open(self.seen_ads_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()

    def save_seen_ads(self):
        with open(self.seen_ads_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.seen_ads), f, ensure_ascii=False, indent=2)

    def update_status(self, running=None, login_waiting=None, message=None):
        """Persist scraper status so dashboard can read it"""
        status = {
            'running': False,
            'login_waiting': False,
            'message': '',
            'timestamp': None
        }
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status.update(json.load(f))
        except Exception:
            pass

        if running is not None:
            status['running'] = running
        if login_waiting is not None:
            status['login_waiting'] = login_waiting
        if message is not None:
            status['message'] = message

        status['timestamp'] = datetime.now().isoformat()

        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def consume_otp_code(self):
        """Read OTP code once and delete the file"""
        try:
            if not os.path.exists(self.otp_file):
                return None
            with open(self.otp_file, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            code = str(payload.get('code', '')).strip()
            os.remove(self.otp_file)
            if code:
                logging.info("OTP code received from dashboard")
            return code or None
        except Exception as e:
            logging.debug(f"Could not read OTP code: {e}")
            return None

    def is_rate_limited(self):
        """Detect too-many-requests block page"""
        try:
            return bool(self.driver.find_elements(By.CSS_SELECTOR, ".error-page-container.too-many-requests"))
        except Exception:
            return False

    def handle_rate_limit_wait(self, wait_seconds=900, retries=2):
        """
        If rate limit page is shown, wait in 15-minute chunks (default 2 tries).
        Returns True if page is cleared, False if still blocked after retries.
        """
        for attempt in range(retries):
            if not self.is_rate_limited():
                return True
            logging.warning(f"Rate limit page detected (attempt {attempt+1}/{retries}). Waiting {wait_seconds//60} minutes...")
            self.update_status(message=f"Rate limit tespit edildi, {wait_seconds//60} dk bekleniyor (deneme {attempt+1}/{retries})")
            time.sleep(wait_seconds)
            logging.info("Retrying after wait...")
            self.driver.refresh()
            time.sleep(5)

        if self.is_rate_limited():
            logging.error("Still blocked by rate limit after retries")
            self.update_status(message="Rate limit devam ediyor, tekrar deneyin veya bekleyin")
            return False
        return True

    def try_submit_otp_if_present(self):
        """If OTP form is visible and an OTP code file exists, submit it"""
        otp_code = self.consume_otp_code()
        if not otp_code:
            return False

        try:
            code_input = self.driver.find_element(By.ID, "code")
            code_input.clear()
            code_input.send_keys(otp_code)

            # Submit form
            submit_btns = self.driver.find_elements(By.CSS_SELECTOR, "#twoFactorAuthenticationForm button[type='submit']")
            if submit_btns:
                submit_btns[0].click()
            else:
                code_input.submit()

            logging.info("OTP submitted from dashboard")
            self.update_status(login_waiting=True, message="OTP gönderildi, doğrulama bekleniyor")
            time.sleep(3)
            return True
        except Exception as e:
            logging.warning(f"OTP submit failed: {e}")
            return False

    def save_cookies(self):
        """Browser cookies'lerini kaydet"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logging.info(f"Cookies saved to {self.cookies_file}")
        except Exception as e:
            logging.error(f"Error saving cookies: {e}")

    def load_cookies(self):
        """Kaydedilmiş cookies'leri yükle"""
        try:
            import os
            if not os.path.exists(self.cookies_file):
                logging.info("No saved cookies found")
                return False

            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            # Önce sahibinden.com'a git (cookie eklemek için domain gerekli)
            self.driver.get('https://www.sahibinden.com')
            time.sleep(2)

            # Cookies'leri ekle
            for cookie in cookies:
                try:
                    # expiry problemi olabilir, sil
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logging.debug(f"Could not add cookie {cookie.get('name')}: {e}")

            logging.info(f"Loaded {len(cookies)} cookies")
            return True
        except Exception as e:
            logging.error(f"Error loading cookies: {e}")
            return False

    def handle_login_if_needed(self, resume_url=None, poll_seconds=5, heartbeat_seconds=60):
        """Login sayfasındaysa cookie/OTP bekleyip yeni cookie yüklenince devam eder"""
        current_url = self.driver.current_url

        if 'login' not in current_url.lower() and 'secure.sahibinden.com' not in current_url:
            return True  # Login'e gerek yok

        logging.warning("=" * 60)
        logging.warning("LOGIN REQUIRED!")
        logging.warning("=" * 60)
        logging.warning(f"Current URL: {current_url}")
        logging.warning("")
        logging.warning("Please login in the browser OR upload fresh cookies via dashboard.")
        logging.warning("1. Email/kullanıcı adı ve şifreyi girin")
        logging.warning("2. OTP doğrulamasını tamamlayın")
        logging.warning("   veya dashboard'da yeni cookie yükleyin")
        logging.warning("3. Ana sayfaya yönlenene kadar bekleyin")
        logging.warning("=" * 60)

        last_cookie_mtime = os.path.getmtime(self.cookies_file) if os.path.exists(self.cookies_file) else 0
        heartbeat_at = time.time()
        self.update_status(login_waiting=True, message="Login/OTP gerekli - dashboard'dan yeni cookie yükleyin")

        while True:
            current_url = self.driver.current_url
            if 'login' not in current_url.lower() and 'secure.sahibinden.com' not in current_url:
                logging.info("Login successful!")
                time.sleep(3)  # Sayfanın tamamen yüklenmesi için
                self.save_cookies()
                self.update_status(login_waiting=False, message="Login tamamlandı, scraping devam ediyor")
                return True

            # Try to submit OTP if form is present and code supplied
            try:
                if self.driver.find_elements(By.ID, "twoFactorAuthenticationForm") and self.driver.find_elements(By.ID, "code"):
                    self.try_submit_otp_if_present()
            except Exception:
                pass

            try:
                if os.path.exists(self.cookies_file):
                    new_mtime = os.path.getmtime(self.cookies_file)
                    if new_mtime > last_cookie_mtime:
                        logging.info("New cookies detected, reloading and retrying login...")
                        last_cookie_mtime = new_mtime
                        self.load_cookies()
                        if resume_url:
                            self.driver.get(resume_url)
                        else:
                            self.driver.refresh()
                        time.sleep(5)
                        continue
            except Exception as e:
                logging.debug(f"Cookie reload check failed: {e}")

            now = time.time()
            if now - heartbeat_at >= heartbeat_seconds:
                logging.warning("Still waiting for login/OTP or fresh cookies... upload via dashboard if needed.")
                heartbeat_at = now
                self.update_status(login_waiting=True, message="Login/OTP gerekli - dashboard'dan yeni cookie yükleyin")

            time.sleep(poll_seconds)

    def get_chrome_options(self):
        """Chrome options oluştur - her seferinde yeni object"""
        options = uc.ChromeOptions()

        # Temel ayarlar
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')

        # Pencere boyutu
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--start-maximized')

        # Bot tespitini zorlaştıran ek ayarlar
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')

        # User agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

        # Dil ayarları
        options.add_argument('--lang=tr-TR')

        return options

    def init_driver(self):
        logging.info("Initializing undetected Chrome driver...")

        try:
            # Version'ı otomatik tespit ettir, headless=False ama Xvfb kullanacağız
            options = self.get_chrome_options()
            self.driver = uc.Chrome(options=options, headless=False, use_subprocess=True)
            logging.info("Driver initialized successfully")

            # JavaScript injection - webdriver flaglerini gizle
            try:
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                })
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                logging.info("Stealth JavaScript injected successfully")
            except Exception as js_error:
                logging.warning(f"Could not inject stealth JavaScript: {js_error}")

            # Saved cookies varsa yükle
            self.load_cookies()

        except Exception as e:
            logging.error(f"Error initializing driver: {e}")
            # Fallback olarak version_main belirterek dene - YENİ options object kullan
            logging.info("Retrying with specific Chrome version...")
            try:
                options = self.get_chrome_options()  # Yeni options object
                self.driver = uc.Chrome(options=options, version_main=131, headless=False, use_subprocess=True)
                logging.info("Driver initialized successfully with version 131")

                # JavaScript injection
                try:
                    self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                    })
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    logging.info("Stealth JavaScript injected successfully")
                except Exception as js_error:
                    logging.warning(f"Could not inject stealth JavaScript: {js_error}")

                # Saved cookies varsa yükle
                self.load_cookies()

            except Exception as retry_error:
                logging.error(f"Failed to initialize driver even with version 131: {retry_error}")
                raise

    def handle_cloudflare_challenge(self):
        try:
            continue_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "btn-continue"))
            )
            logging.info("Cloudflare Turnstile challenge detected!")
            logging.info("Waiting for Turnstile widget to load...")
            time.sleep(5)

            logging.info("Clicking 'Devam Et' button...")
            continue_button.click()

            logging.info("Waiting for challenge to complete...")
            time.sleep(8)

            return True
        except:
            return False

    def get_listings(self, url, brand_name):
        logging.info(f"Navigating to: {url}")
        self.driver.get(url)

        # İlk bekleme - sayfanın yüklenmesi için
        time.sleep(7)

        # Login sayfasına yönlendirildik mi kontrol et
        current_url = self.driver.current_url
        if 'login' in current_url.lower() or 'secure.sahibinden.com' in current_url:
            logging.warning("Redirected to login page")
            logging.info(f"Current URL: {current_url}")

            # Manuel login'i bekle
            if not self.handle_login_if_needed(resume_url=url):
                logging.error("Login failed or timeout - skipping this brand")
                self.driver.save_screenshot("login_failed.png")
                return []

            # Login başarılı, sayfayı yeniden yükle
            logging.info("Login successful, reloading search page...")
            self.driver.get(url)
            time.sleep(7)

        # Cloudflare challenge kontrolü
        if self.handle_cloudflare_challenge():
            logging.info("Cloudflare challenge handled, continuing...")
            time.sleep(5)

        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "searchResultsItem"))
            )
            logging.info("Search results page loaded")
            time.sleep(2)  # Sayfanın tamamen render olması için
        except Exception as e:
            logging.error(f"Error loading search results: {e}")
            logging.info("Current URL: " + self.driver.current_url)
            logging.info("Saving screenshot for debugging...")
            self.driver.save_screenshot("error_screenshot.png")
            return []

        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        listings = []
        tbody_elements = soup.find_all('tbody', class_='searchResultsRowClass')

        for tbody in tbody_elements:
            rows = tbody.find_all('tr', class_='searchResultsItem')

            for row in rows:
                if 'nativeAd' in row.get('class', []):
                    continue

                listing_id = row.get('data-id')
                if not listing_id:
                    continue

                title_elem = row.find('a', class_='classifiedTitle')
                if not title_elem:
                    continue

                title = title_elem.get('title', '')
                url = title_elem.get('href', '')

                if url and not url.startswith('http'):
                    url = 'https://www.sahibinden.com' + url

                year_elem = row.find_all('td', class_='searchResultsAttributeValue')
                price_elem = row.find('td', class_='searchResultsPriceValue')
                location_elem = row.find('td', class_='searchResultsLocationValue')

                year = year_elem[0].text.strip() if len(year_elem) > 0 else 'N/A'
                km = year_elem[1].text.strip() if len(year_elem) > 1 else 'N/A'
                color = year_elem[2].text.strip() if len(year_elem) > 2 else 'N/A'

                price = 'N/A'
                if price_elem:
                    price_span = price_elem.find('span')
                    if price_span:
                        price = price_span.text.strip()

                location = 'N/A'
                if location_elem:
                    location = location_elem.text.strip().replace('\n', ' ')

                listing = {
                    'id': listing_id,
                    'title': title,
                    'url': url,
                    'year': year,
                    'km': km,
                    'color': color,
                    'price': price,
                    'location': location,
                    'brand': brand_name
                }

                listings.append(listing)
                logging.info(f"Found listing: {listing_id} - {title}")

        logging.info(f"Total listings found: {len(listings)}")
        return listings

    def get_damage_info(self, listing_url):
        logging.info(f"Checking damage info for: {listing_url}")
        self.driver.get(listing_url)

        # Daha uzun bekleme - insan gibi davranmak için
        time.sleep(5)

        # Rate limit kontrolü: 15 dk bekle, tekrar aynıysa bir 15 dk daha bekle
        if self.is_rate_limited():
            if not self.handle_rate_limit_wait():
                logging.warning("Rate limit kalkmadı, ilan atlanıyor")
                return None

        # Login kontrolü
        if 'login' in self.driver.current_url.lower():
            logging.warning("Redirected to login on detail page")

            # Manuel login'i bekle
            if not self.handle_login_if_needed(resume_url=listing_url):
                logging.error("Login failed - cannot get damage info")
                return None

            # Login başarılı, detail sayfasını yeniden yükle
            self.driver.get(listing_url)
            time.sleep(5)

        if self.handle_cloudflare_challenge():
            logging.info("Cloudflare challenge handled on detail page, continuing...")
            time.sleep(4)

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "custom-area"))
            )
        except Exception as e:
            logging.warning(f"Could not find damage area: {e}")
            return None

        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        damage_area = soup.find('div', class_='custom-area')
        if not damage_area:
            logging.warning("No damage area found")
            return None

        painted_parts = []
        replaced_parts = []
        local_painted_parts = []

        info_list = damage_area.find('div', class_='car-damage-info-list')
        if info_list:
            uls = info_list.find_all('ul')

            for ul in uls:
                title = ul.find('li', class_='pair-title')
                if not title:
                    continue

                title_text = title.text.strip()
                parts = ul.find_all('li', class_='selected-damage')
                part_names = [part.text.strip() for part in parts]

                if 'Boyalı' in title_text and 'painted-new' in title.get('class', []):
                    painted_parts = part_names
                elif 'Değişen' in title_text and 'changed-new' in title.get('class', []):
                    replaced_parts = part_names
                elif 'Lokal' in title_text:
                    local_painted_parts = part_names

        # Kaput kontrolü - Kaputun temiz olması gerekiyor
        hood_keywords = ['kaput', 'ön kaput', 'motor kaputu']
        hood_damaged = False
        hood_damage_type = None

        for keyword in hood_keywords:
            # Boyalı kontrolü
            if any(keyword.lower() in part.lower() for part in painted_parts):
                hood_damaged = True
                hood_damage_type = 'boyalı'
                break
            # Değişen kontrolü
            if any(keyword.lower() in part.lower() for part in replaced_parts):
                hood_damaged = True
                hood_damage_type = 'değişen'
                break
            # Lokal boyalı kontrolü
            if any(keyword.lower() in part.lower() for part in local_painted_parts):
                hood_damaged = True
                hood_damage_type = 'lokal boyalı'
                break

        damage_info = {
            'painted_parts': painted_parts,
            'replaced_parts': replaced_parts,
            'local_painted_parts': local_painted_parts,
            'painted_count': len(painted_parts),
            'replaced_count': len(replaced_parts),
            'local_painted_count': len(local_painted_parts),
            'hood_damaged': hood_damaged,
            'hood_damage_type': hood_damage_type
        }

        logging.info(f"Damage info - Replaced: {damage_info['replaced_count']}, Painted: {damage_info['painted_count']}, Local Painted: {damage_info['local_painted_count']}, Hood: {'✗ ' + hood_damage_type if hood_damaged else '✓ Temiz'}")

        return damage_info

    def check_listing(self, listing):
        if listing['id'] in self.seen_ads:
            logging.info(f"Skipping already seen listing: {listing['id']}")
            return False

        damage_info = self.get_damage_info(listing['url'])

        if damage_info is None:
            logging.info(f"Skipping listing {listing['id']} - No damage info available")
            self.seen_ads.add(listing['id'])
            return False

        listing['damage_info'] = damage_info

        replaced_count = damage_info['replaced_count']
        painted_count = damage_info['painted_count']
        hood_damaged = damage_info['hood_damaged']
        hood_damage_type = damage_info['hood_damage_type']

        self.seen_ads.add(listing['id'])

        # Kaput hasarlı ise direkt reddet
        if hood_damaged:
            logging.info(f"✗ REJECTED: {listing['title']}")
            logging.info(f"  KAPUT HASARLI: {hood_damage_type}")
            logging.info(f"  Replaced parts: {replaced_count}/{self.max_replaced_parts}")
            logging.info(f"  Painted parts: {painted_count}/{self.max_painted_parts}")
            return False

        if replaced_count <= self.max_replaced_parts and painted_count <= self.max_painted_parts:
            logging.info(f"✓ ACCEPTED: {listing['title']}")
            logging.info(f"  Hood: ✓ Temiz")
            logging.info(f"  Replaced parts: {replaced_count}/{self.max_replaced_parts}")
            logging.info(f"  Painted parts: {painted_count}/{self.max_painted_parts}")
            logging.info(f"  Price: {listing['price']}")
            logging.info(f"  URL: {listing['url']}")
            self.filtered_listings.append(listing)
            return True
        else:
            logging.info(f"✗ REJECTED: {listing['title']}")
            logging.info(f"  Hood: ✓ Temiz")
            logging.info(f"  Replaced parts: {replaced_count}/{self.max_replaced_parts} (exceeded)" if replaced_count > self.max_replaced_parts else f"  Replaced parts: {replaced_count}/{self.max_replaced_parts}")
            logging.info(f"  Painted parts: {painted_count}/{self.max_painted_parts} (exceeded)" if painted_count > self.max_painted_parts else f"  Painted parts: {painted_count}/{self.max_painted_parts}")
            return False

    def run_single_check(self):
        self.filtered_listings = []

        try:
            self.update_status(running=True, login_waiting=False, message="Scrape cycle started")
            if not self.driver:
                self.init_driver()

            enabled_brands = [b for b in self.config.get('brands', []) if b.get('enabled', True)]

            if not enabled_brands:
                logging.warning("No enabled brands in config")
                self.update_status(message="No enabled brands in config")
                return

            for brand in enabled_brands:
                brand_name = brand.get('name', 'Unknown')
                url = brand.get('url', '')

                if not url:
                    continue

                logging.info(f"\n{'='*60}")
                logging.info(f"Checking brand: {brand_name}")
                logging.info(f"{'='*60}")

                listings = self.get_listings(url, brand_name)

                if not listings:
                    logging.warning(f"No listings found for {brand_name}")
                    continue

                logging.info(f"Processing {len(listings)} listings for {brand_name}...")

                for idx, listing in enumerate(listings, 1):
                    logging.info(f"\n--- Processing listing {idx}/{len(listings)} ---")
                    self.check_listing(listing)
                    # Random delay between listings (3-7 seconds)
                    delay = random.uniform(3, 7)
                    logging.info(f"Waiting {delay:.1f}s before next listing...")
                    time.sleep(delay)

            self.save_seen_ads()
            self.save_results()

            if self.filtered_listings:
                logging.info(f"\n{len(self.filtered_listings)} new listings found! Sending email...")
                logging.info(f"{'='*60}")
                logging.info("EMAIL CONTENT:")
                logging.info(f"{'='*60}")
                for listing in self.filtered_listings:
                    logging.info(f"• {listing['title']}")
                    logging.info(f"  Marka: {listing.get('brand', 'N/A')}")
                    logging.info(f"  Fiyat: {listing['price']}")
                    logging.info(f"  Yıl: {listing['year']} | KM: {listing['km']}")
                    logging.info(f"  Boya: {listing['damage_info']['painted_count']} | Değişen: {listing['damage_info']['replaced_count']}")
                    logging.info(f"  Link: {listing['url']}")
                    logging.info("")
                logging.info(f"{'='*60}")

                if self.email_sender.send_listings_email(self.filtered_listings):
                    logging.info("Email sent successfully!")
                else:
                    logging.warning("Failed to send email")
            else:
                logging.info("No new listings matching criteria")

        except Exception as e:
            logging.error(f"Error during scraping: {e}", exc_info=True)
            self.update_status(message=f"Error during scraping: {e}")

    def run(self):
        try:
            logging.info("Starting Sahibinden Scraper...")
            logging.info(f"Check interval: {self.config.get('check_interval_minutes', 30)} minutes")
            logging.info(f"Max replaced parts: {self.max_replaced_parts}")
            logging.info(f"Max painted parts: {self.max_painted_parts}")
            self.update_status(running=True, login_waiting=False, message="Scraper started")

            self.run_single_check()

            interval = self.config.get('check_interval_minutes', 30)
            schedule.every(interval).minutes.do(self.run_single_check)

            logging.info(f"\nScheduler started. Checking every {interval} minutes...")
            logging.info("Press Ctrl+C to stop")

            while True:
                schedule.run_pending()
                time.sleep(60)

        except KeyboardInterrupt:
            logging.info("\nStopping scraper...")
        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)
            self.update_status(message=f"Error in main loop: {e}")
        finally:
            if self.driver:
                logging.info("Closing browser...")
                try:
                    self.driver.quit()
                except:
                    pass
            self.update_status(running=False, login_waiting=False, message="Scraper stopped")

    def save_results(self):
        filename = os.path.join(self.data_dir, 'filtered_listings.json')
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.filtered_listings, f, ensure_ascii=False, indent=2)

        logging.info(f"\n{'='*60}")
        logging.info(f"SUMMARY")
        logging.info(f"{'='*60}")
        logging.info(f"Total new accepted listings: {len(self.filtered_listings)}")
        logging.info(f"Results saved to: {filename}")
        logging.info(f"{'='*60}")

if __name__ == "__main__":
    scraper = SahibindenScraper()
    scraper.run()
