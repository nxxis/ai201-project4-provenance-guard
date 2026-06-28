import urllib.request
import json

def submit(text, creator_id):
    data = json.dumps({"text": text, "creator_id": creator_id}).encode()
    req = urllib.request.Request(
        "http://localhost:5000/submit",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    return json.loads(urllib.request.urlopen(req).read())

def appeal(content_id, reasoning):
    data = json.dumps({"content_id": content_id, "creator_reasoning": reasoning}).encode()
    req = urllib.request.Request(
        "http://localhost:5000/appeal",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    return json.loads(urllib.request.urlopen(req).read())

# --- Label variants ---
ai_result = submit(
    "It is important to note that artificial intelligence represents a transformative paradigm shift. Furthermore, stakeholders must collaborate to ensure responsible deployment across various sectors.",
    "label-test-ai"
)
print("=== LIKELY AI ===")
print(f"confidence: {ai_result['confidence']}  attribution: {ai_result['attribution']}")
print(f"label:\n{ai_result['label']}\n")

human_result = submit(
    "ok so i finally tried that ramen place and honestly? underwhelming. broth was fine but way too salty, was thirsty for hours after",
    "label-test-human"
)
print("=== LIKELY HUMAN ===")
print(f"confidence: {human_result['confidence']}  attribution: {human_result['attribution']}")
print(f"label:\n{human_result['label']}\n")

uncertain_result = submit(
    "There are several key factors to consider when choosing a laptop. First, battery life is crucial for students. Second, processing power matters a lot for gaming. Also it honestly depends on your budget lol. Overall, the decision requires careful consideration of individual needs.",
    "label-test-uncertain"
)
print("=== UNCERTAIN ===")
print(f"confidence: {uncertain_result['confidence']}  attribution: {uncertain_result['attribution']}")
print(f"label:\n{uncertain_result['label']}\n")

# --- Appeal test ---
print("=== APPEAL ===")
appeal_result = appeal(
    human_result["content_id"],
    "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."
)
print(json.dumps(appeal_result, indent=2))