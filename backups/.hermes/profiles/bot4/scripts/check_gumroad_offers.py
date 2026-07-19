#!/usr/bin/env python3
"""Check Gumroad offers API."""
import json, os, urllib.request

token = "rbv34dFT7tychocAS5kKiqyvTjpRkwgFhaNr81nVnPY"

# Check if we can list offers for the TikTok product
url = f"https://api.gumroad.com/v2/products/diywdak/offer_codes"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print("OFFERS for diywdak:")
    print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
    # Try the resource/subscription version
    url2 = "https://api.gumroad.com/v2/resource_subscriptions"
    req2 = urllib.request.Request(url2, headers={"Authorization": f"Bearer {token}"})
    try:
        resp2 = urllib.request.urlopen(req2)
        data2 = json.loads(resp2.read())
        print("\nRESOURCE SUBS:")
        print(json.dumps(data2, indent=2))
    except Exception as e2:
        print(f"Resource sub error: {e2}")

# Also check me endpoint
print("\n--- ME ---")
url3 = "https://api.gumroad.com/v2/user"
req3 = urllib.request.Request(url3, headers={"Authorization": f"Bearer {token}"})
try:
    resp3 = urllib.request.urlopen(req3)
    data3 = json.loads(resp3.read())
    print(json.dumps(data3, indent=2))
except Exception as e3:
    print(f"User error: {e3}")
