"""
E-posta gönderme modülü
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    def __init__(self):
        self.host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
        self.port = int(os.getenv('EMAIL_PORT', '587'))
        self.user = os.getenv('EMAIL_USER', '')
        self.password = os.getenv('EMAIL_PASSWORD', '')
        self.to_email = os.getenv('TO_EMAIL', '')
    
    def send_listings_email(self, listings):
        """
        İlanları içeren e-posta gönderir
        """
        if not listings:
            return False
        
        if not self.user or not self.password or not self.to_email:
            error_msg = f"E-posta ayarları eksik! user={bool(self.user)}, password={bool(self.password)}, to_email={bool(self.to_email)}"
            print(error_msg)
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Sahibinden - {len(listings)} Yeni İlan Bulundu!'
            msg['From'] = self.user
            msg['To'] = self.to_email
            
            # HTML içerik oluştur
            html_content = self._create_html_content(listings)
            text_content = self._create_text_content(listings)
            
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            
            print(f"{len(listings)} ilan için e-posta gönderildi!")
            return True
            
        except Exception as e:
            print(f"E-posta gönderme hatası: {e}")
            return False
    
    def _create_html_content(self, listings):
        """
        HTML formatında e-posta içeriği oluşturur
        """
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f4;
                    padding: 20px;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                h2 {{
                    color: #333;
                    border-bottom: 3px solid #FFD800;
                    padding-bottom: 10px;
                }}
                .listing {{
                    background-color: #f9f9f9;
                    border-left: 4px solid #FFD800;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .title {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .title a {{
                    color: #0066cc;
                    text-decoration: none;
                }}
                .title a:hover {{
                    text-decoration: underline;
                }}
                .price {{
                    font-size: 24px;
                    color: #e74c3c;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .details {{
                    color: #666;
                    margin: 10px 0;
                    line-height: 1.6;
                }}
                .detail-row {{
                    margin: 5px 0;
                }}
                .label {{
                    font-weight: bold;
                    color: #333;
                }}
                .damage-info {{
                    background-color: #e8f5e9;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
                .btn {{
                    display: inline-block;
                    background-color: #FFD800;
                    color: #333;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                }}
                .btn:hover {{
                    background-color: #FFC700;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🚗 Sahibinden - Yeni İlanlar</h2>
                <p>Belirlediğiniz kriterlere uygun <strong>{count}</strong> yeni ilan bulundu:</p>
        """.format(count=len(listings))

        for listing in listings:
            price = listing.get('price', 'N/A')
            year = listing.get('year', 'N/A')
            km = listing.get('km', 'N/A')
            brand = listing.get('brand', 'N/A')
            color = listing.get('color', 'N/A')
            location = listing.get('location', 'N/A')
            damage_info = listing.get('damage_info', {})
            painted_count = damage_info.get('painted_count', 0)
            replaced_count = damage_info.get('replaced_count', 0)
            painted_parts = damage_info.get('painted_parts', [])
            replaced_parts = damage_info.get('replaced_parts', [])

            html += f"""
            <div class="listing">
                <div class="title">
                    <a href="{listing.get('url', '#')}" target="_blank">{listing.get('title', 'Başlık Yok')}</a>
                </div>
                <div class="price">{price}</div>
                <div class="details">
                    <div class="detail-row"><span class="label">Marka:</span> {brand}</div>
                    <div class="detail-row"><span class="label">Yıl:</span> {year} | <span class="label">Kilometre:</span> {km}</div>
                    <div class="detail-row"><span class="label">Renk:</span> {color}</div>
                    <div class="detail-row"><span class="label">Lokasyon:</span> {location}</div>
                </div>
                <div class="damage-info">
                    <div class="detail-row">
                        <span class="label">🚗 Kaput:</span> <strong style="color: #27ae60;">✓ TEMİZ</strong>
                    </div>
                    <div class="detail-row">
                        <span class="label">✅ Boyalı Parça:</span> {painted_count}
                        {f"({', '.join(painted_parts)})" if painted_parts else ""}
                    </div>
                    <div class="detail-row">
                        <span class="label">🔧 Değişen Parça:</span> {replaced_count}
                        {f"({', '.join(replaced_parts)})" if replaced_parts else ""}
                    </div>
                </div>
                <a href="{listing.get('url', '#')}" class="btn" target="_blank">İlanı Görüntüle</a>
            </div>
            """

        html += """
            </div>
        </body>
        </html>
        """
        return html
    
    def _create_text_content(self, listings):
        """
        Düz metin formatında e-posta içeriği oluşturur
        """
        text = f"Sahibinden - Yeni İlanlar\n\n"
        text += f"Belirlediğiniz kriterlere uygun {len(listings)} yeni ilan bulundu:\n\n"
        
        for i, listing in enumerate(listings, 1):
            text += f"{i}. {listing.get('title', 'Başlık Yok')}\n"
            text += f"   Fiyat: {listing.get('price', 'N/A')}\n"
            if listing.get('year'):
                text += f"   Yıl: {listing.get('year')}\n"
            if listing.get('km'):
                text += f"   KM: {listing.get('km')}\n"
            text += f"   Link: {listing.get('url', '#')}\n\n"
        
        return text

