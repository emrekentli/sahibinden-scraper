"""
Email formatını test etmek için basit script
"""
from email_sender import EmailSender

# Test verisi
test_listing = [{
    'id': '1286652975',
    'title': '2020 MODEL RIO 1.4 ELEGANCE TEKNO SADECE 31 BİN KM',
    'url': 'https://www.sahibinden.com/ilan/vasita-otomobil-kia-2020-model-rio-1.4-elegance-tekno-sadece-31-bin-km-1286652975/detay',
    'year': '2020',
    'km': '31.000',
    'color': 'Mavi',
    'price': '1.039.850 TL',
    'location': 'İstanbul Pendik',
    'brand': 'Kia Rio',
    'damage_info': {
        'painted_parts': ['Sol Arka Kapı', 'Sol Arka Çamurluk'],
        'replaced_parts': ['Sol Ön Çamurluk'],
        'local_painted_parts': [],
        'painted_count': 2,
        'replaced_count': 1,
        'local_painted_count': 0
    }
}]

email_sender = EmailSender()
print("Test email gönderiliyor...")
if email_sender.send_listings_email(test_listing):
    print("✓ Email başarıyla gönderildi!")
else:
    print("✗ Email gönderilemedi")
