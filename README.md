# Sahibinden İlan Takip Uygulaması

Sahibinden.com'dan belirlediğiniz kriterlere uygun ilanları otomatik olarak takip eder ve size e-posta ile bildirir.

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env` dosyası oluşturun ve e-posta ayarlarınızı ekleyin:
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
TO_EMAIL=recipient@example.com
```

**Gmail için önemli:** Uygulama Şifresi (App Password) kullanmanız gerekir.

3. `config.json` dosyasını düzenleyerek arama kriterlerinizi belirleyin.

4. Uygulamayı çalıştırın:
```bash
python sahibinden_scraper.py
```

## Özellikler

- **CloudFlare Bypass**: Undetected ChromeDriver ile CloudFlare Turnstile korumasını aşar
- **Çoklu Marka Desteği**: Aynı anda birden fazla marka/model takip edebilir
- **Akıllı Filtreleme**: Boya ve değişen parça sayısına göre otomatik filtreleme
  - Varsayılan: Max 1 değişen, Max 2 boyalı parça
- **E-posta Bildirimleri**: Kriterlere uygun ilanları HTML formatında e-posta ile gönderir
- **Otomatik Periyodik Kontrol**: Belirlediğiniz aralıklarla (varsayılan 30 dakika) otomatik kontrol
- **Akıllı İlan Takibi**: Daha önce görülen ilanları tekrar bildirmez (seen_ads.json)
- **Detaylı Loglama**: Konsol ve dosya üzerinden tüm işlemleri loglar

## Yapılandırma (config.json)

```json
{
  "check_interval_minutes": 30,
  "max_replaced_parts": 1,
  "max_painted_parts": 2,
  "brands": [
    {
      "name": "Kia Rio",
      "url": "https://www.sahibinden.com/kia-rio-1.4-cvvt-elegance-tekno?...",
      "enabled": true
    },
    {
      "name": "Honda Civic",
      "url": "https://www.sahibinden.com/honda-civic?...",
      "enabled": true
    }
  ]
}
```

### Yeni Marka Ekleme

1. Sahibinden.com'da arama yapın ve filtreleri uygulayın
2. URL'yi kopyalayın
3. `config.json` dosyasındaki `brands` dizisine yeni bir obje ekleyin:

```json
{
  "name": "Marka Model",
  "url": "sahibinden-url-buraya",
  "enabled": true
}
```

## Çıktılar

- `filtered_listings.json`: Kriterlere uygun ilanlar
- `sahibinden_scraper.log`: Tüm işlem logları
- `seen_ads.json`: Görülen ilan ID'leri
- `error_screenshot.png`: Hata durumunda ekran görüntüsü

## Kullanım İpuçları

- Chrome tarayıcısı görünür modda çalışır, işlemleri izleyebilirsiniz
- Ctrl+C ile güvenli şekilde durdurabilirsiniz
- `seen_ads.json` dosyasını silerseniz tüm ilanlar yeniden kontrol edilir
- Geçici olarak bir markayı devre dışı bırakmak için `"enabled": false` yapın

## Notlar

- Uygulama sürekli çalışacak şekilde tasarlanmıştır
- CloudFlare challenge manuel müdahale gerektirebilir (Devam Et butonu)
- Her ilan arasında 2 saniye beklenir (rate limiting)

