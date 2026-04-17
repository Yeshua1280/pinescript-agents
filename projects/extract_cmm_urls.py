import requests
import re

url = "https://app.coinmarketman.com/assets/index-Dd1EDnFA.js"
print("Fetching JS file...")
response = requests.get(url)
content = response.text

print("Searching for API URLs...")
# Find strings starting with http or https, that contain 'api' or 'hypertracker'
urls = re.findall(r'https?://[a-zA-Z0-9.-]+/[a-zA-Z0-9./-]+', content)

unique_urls = set()
for u in urls:
    if 'api' in u or 'hypertracker' in u or 'cohort' in u:
        unique_urls.add(u)

print("Found URLs:")
for u in sorted(unique_urls):
    print(f" - {u}")
