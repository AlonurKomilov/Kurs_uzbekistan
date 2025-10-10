import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://kapitalbank.uz/en/services/exchange-rates/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def fetch_kapitalbank_html():
    response = requests.get(URL, headers=HEADERS, timeout=20, verify=False)
    print(f"Status: {response.status_code}")
    print(f"Encoding: {response.encoding}")
    print(f"Apparent Encoding: {response.apparent_encoding}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    print(f"Content-Encoding: {response.headers.get('content-encoding')}")
    html = response.text
    print(f"HTML length: {len(html)}")
    print(f"First 200 chars: {html[:200]}")
    with open("/tmp/kapitalbank_standalone.html", "w", encoding="utf-8") as f:
        f.write(html)
    return html

def parse_rates(html):
    soup = BeautifulSoup(html, "html.parser")
    rate_boxes = soup.find_all('div', class_='kapitalbank_currency_tablo_rate_box')
    print(f"Found {len(rate_boxes)} rate boxes")
    for box in rate_boxes:
        print(box.text.strip())

if __name__ == "__main__":
    html = fetch_kapitalbank_html()
    parse_rates(html)
