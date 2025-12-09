# Python 3.11 slim image kullan
FROM python:3.11-slim

# Sistem bağımlılıklarını kur (Chrome için gerekli)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    libxi6 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    fonts-liberation \
    ca-certificates \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Google Chrome'u kur (modern yöntem)
RUN wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y /tmp/google-chrome.deb && \
    rm /tmp/google-chrome.deb && \
    rm -rf /var/lib/apt/lists/*

# Çalışma dizinini oluştur
WORKDIR /app

# Requirements dosyasını kopyala ve bağımlılıkları kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# .env dosyası için placeholder (Coolify'da secrets olarak girilecek)
# ENV dosyası Coolify'dan gelecek

# Seen ads dosyası için volume mount noktası
RUN mkdir -p /app/data

# Chrome çalıştırma için gerekli
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome

# Startup script'i kopyala
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
