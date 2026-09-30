import os,requests

K=os.getenv("TP_API_KEY","").strip()

print("KEY PRESENT:",bool(K))
print("KEY PREFIX:",K[:8] if K else "NONE")

r=requests.get(
    "https://trader-pro.org/data/v1/account",
    headers={"X-TP-API-Key":K},
    timeout=20
)

print("HTTP:",r.status_code)
print(r.text[:2000])
