import urllib.request
import json

tests = [
    {
        "label": "Test 1 - Clearly AI",
        "payload": {
            "text": "It is important to note that artificial intelligence represents a transformative paradigm shift. Furthermore, stakeholders must collaborate to ensure responsible deployment across various sectors.",
            "creator_id": "test-ai"
        }
    },
    {
        "label": "Test 2 - Clearly Human",
        "payload": {
            "text": "ok so i finally tried that ramen place and honestly? underwhelming. broth was fine but way too salty, was thirsty for hours after",
            "creator_id": "test-human"
        }
    },
    {
        "label": "Test 3 - Borderline Formal Human",
        "payload": {
            "text": "The relationship between monetary policy and asset price inflation has been extensively studied. Central banks face a fundamental tension between price stability and the consequences of prolonged low interest rates on equity valuations.",
            "creator_id": "test-border1"
        }
    },
    {
        "label": "Test 4 - Borderline Lightly Edited AI",
        "payload": {
            "text": "I've been thinking a lot about remote work lately. There are genuine tradeoffs - flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type.",
            "creator_id": "test-border2"
        }
    },
]

for test in tests:
    data = json.dumps(test["payload"]).encode()
    req = urllib.request.Request(
        "http://localhost:5000/submit",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    result = json.loads(urllib.request.urlopen(req).read())
    print(f"\n{test['label']}")
    print(f"  llm_score:         {result.get('llm_score')}")
    print(f"  stylometric_score: {result.get('stylometric_score')}")
    print(f"  confidence:        {result.get('confidence')}")
    print(f"  attribution:       {result.get('attribution')}")