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
    libgconf-2-4 \
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
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Google Chrome'u kur
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
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

# Xvfb (virtual display) başlat ve uygulamayı çalıştır
CMD Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp & python sahibinden_scraper.py
