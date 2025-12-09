import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
import logging
import schedule
from datetime import datetime
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
        import os
        self.seen_ads_file = '/app/data/seen_ads.json' if os.path.exists('/app/data') else 'seen_ads.json'
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

    def init_driver(self):
        logging.info("Initializing undetected Chrome driver...")
        options = uc.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        self.driver = uc.Chrome(options=options, version_main=142, headless=False, use_subprocess=False)

        logging.info("Driver initialized successfully")

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

        time.sleep(5)

        if self.handle_cloudflare_challenge():
            logging.info("Cloudflare challenge handled, continuing...")
            time.sleep(3)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "searchResultsItem"))
            )
            logging.info("Search results page loaded")
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

        time.sleep(3)

        if self.handle_cloudflare_challenge():
            logging.info("Cloudflare challenge handled on detail page, continuing...")
            time.sleep(3)

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
            if not self.driver:
                self.init_driver()

            enabled_brands = [b for b in self.config.get('brands', []) if b.get('enabled', True)]

            if not enabled_brands:
                logging.warning("No enabled brands in config")
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
                    time.sleep(2)

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

    def run(self):
        try:
            logging.info("Starting Sahibinden Scraper...")
            logging.info(f"Check interval: {self.config.get('check_interval_minutes', 30)} minutes")
            logging.info(f"Max replaced parts: {self.max_replaced_parts}")
            logging.info(f"Max painted parts: {self.max_painted_parts}")

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
        finally:
            if self.driver:
                logging.info("Closing browser...")
                try:
                    self.driver.quit()
                except:
                    pass

    def save_results(self):
        filename = 'filtered_listings.json'
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
