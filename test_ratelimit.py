import urllib.request
import urllib.error
import json

print("Sending 12 rapid requests to /submit...")
print("Expecting: 200 for first 10, 429 for last 2\n")

for i in range(1, 13):
    data = json.dumps({
        "text": "This is a rate limit test submission.",
        "creator_id": "ratelimit-test"
    }).encode()

    req = urllib.request.Request(
        "http://localhost:5000/submit",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        urllib.request.urlopen(req)
        print(f"Request {i:2d}: 200")
    except urllib.error.HTTPError as e:
        print(f"Request {i:2d}: {e.code}")