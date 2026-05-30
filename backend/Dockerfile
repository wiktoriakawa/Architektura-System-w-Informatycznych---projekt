FROM python:3.12-slim

WORKDIR /app

# Zależności systemowe dla psycopg2 + dos2unix do naprawy końcówek linii CRLF
# pochodzących z Windows / OneDrive (chronimy entrypoint.sh przed psuciem przez bash).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev dos2unix && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Konwersja wszystkich skryptów i plików tekstowych z CRLF na LF — kontener
# Linuxowy nie znosi CRLF w plikach uruchamianych przez bash i Pythona.
RUN find . -type f \( -name "*.sh" -o -name "*.py" -o -name "*.ini" \) \
    -exec dos2unix -q {} \; && \
    chmod +x entrypoint.sh

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
