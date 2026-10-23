import os
import json

from dotenv import load_dotenv
import httpx

load_dotenv()

api_key = os.environ["OPERATOR_LLM_API_KEY"]
base_url = os.environ["OPERATOR_LLM_BASE_URL"].rstrip("/")
model = os.environ["OPERATOR_LLM_MODEL"]

url = f"{base_url}/responses"

payload = {
    "model": model,
    "input": "Reply exactly with: OK",
}

print("URL:", url)
print("MODEL:", model)
print("API KEY CONFIGURED:", bool(api_key))

with httpx.Client(timeout=120.0) as client:
    response = client.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

print("STATUS:", response.status_code)

print("RESPONSE HEADERS:")
for key in (
    "content-type",
    "request-id",
    "x-request-id",
    "cf-ray",
    "server",
    "retry-after",
):
    if key in response.headers:
        print(f"  {key}: {response.headers[key]}")

print("BODY:")
try:
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
except Exception:
    print(response.text)