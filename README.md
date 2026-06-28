# Provenance Guard

A backend API system that classifies submitted text as human-written or AI-generated, scores confidence in that classification, surfaces a transparency label to users, and handles creator appeals. Built for AI201 (CodePath).

---

## Architecture Overview

A submitted piece of text takes the following path through the system:

1. **`POST /submit`** receives `text` and `creator_id` in a JSON request body and generates a unique `content_id` for the submission.
2. **Signal 1 — Groq LLM classification**: the text is sent to `llama-3.3-70b-versatile` with a structured prompt. The model returns a single `llm_score` float (0–1) reflecting how strongly the text reads as AI-generated based on semantic and stylistic patterns.
3. **Signal 2 — Stylometric heuristics**: two structural metrics are computed in pure Python — sentence length variance and type-token ratio (TTR). Both are normalized and averaged into a single `stylometric_score` float (0–1).
4. **Confidence scoring**: both signal scores are combined via weighted average (`0.6 × llm_score + 0.4 × stylometric_score`) into a single `confidence` value and mapped to an `attribution` string (`likely_ai`, `uncertain`, or `likely_human`).
5. **Label generation**: the confidence score selects one of three transparency label variants, returned as plain text in the response.
6. **Audit log**: a structured JSON entry capturing all fields — both signal scores, combined confidence, attribution, label, and status — is appended to `audit_log.json`.
7. The API returns `content_id`, `attribution`, `confidence`, `label`, `llm_score`, and `stylometric_score`.

Appeals arrive via **`POST /appeal`** with a `content_id` and `creator_reasoning`. The system looks up the original entry in the audit log, updates its `status` to `under_review`, appends the appeal reasoning and timestamp, and returns a confirmation. No automated re-classification occurs.

```
SUBMISSION FLOW
===============
POST /submit
  │  {text, creator_id}
  ▼
┌─────────────────────┐
│  Signal 1: Groq LLM │──► llm_score (0–1)
└─────────────────────┘         │
                                ▼
┌──────────────────────────┐  ┌────────────────────┐
│ Signal 2: Stylometrics   │  │  Confidence Scorer  │
│ (sent-len var + TTR)     │─►│  (weighted combine) │──► confidence (0–1)
└──────────────────────────┘  └────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │   Label Generator    │──► label text
                              └─────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │   JSON Audit Log     │──► appends entry
                              └─────────────────────┘
                                         │
                              ◄──────────┘
               {content_id, attribution, confidence, label}

APPEAL FLOW
===========
POST /appeal
  │  {content_id, creator_reasoning}
  ▼
┌───────────────────────────────────────┐
│  Look up entry in JSON log            │
│  Update status → "under_review"       │
│  Append appeal_reasoning +            │
│  appeal_timestamp to entry            │
└───────────────────────────────────────┘
  │
  ▼
{confirmed: true, status: "under_review", content_id: "..."}
```

---

## Detection Signals

### Signal 1 — Groq LLM Classification

**What it measures:** Semantic and stylistic coherence. The model assesses whether the text reads as AI-generated based on patterns like hedged phrasing ("it is important to note"), overly structured argumentation, uniform sentence rhythm, and generic vocabulary choices. This is a holistic judgment — the model considers the entire text as a unit.

**Why chosen:** LLM-based classification captures properties that no statistical metric can — the "feel" of AI writing at the semantic level. It is the strongest single signal available for this task.

**What it misses:** A polished, deliberate human writer (academic, legal, technical) will produce text that reads as AI-generated to this signal. Conversely, a well-prompted LLM that mimics casual voice can evade it. The signal operates on perceived style, not ground-truth authorship.

**Output:** A float in [0.0, 1.0] where 1.0 = highly confident AI-generated.

---

### Signal 2 — Stylometric Heuristics

**What it measures:** Statistical structural properties of the text. Two metrics are computed:

- **Sentence length variance**: the variance in word count across sentences. AI writing clusters tightly around a consistent mean; human writing is more irregular.
- **Type-token ratio (TTR)**: unique words divided by total words. Human writing (especially casual or creative) tends to be more lexically diverse; AI writing shows moderate, uniform TTR.

Both metrics are normalized to [0, 1] and averaged into a single `stylometric_score`.

**Why chosen:** This signal is structurally independent from Signal 1 — it measures mathematical properties of the text, not semantic content. When both signals agree, the combined confidence is high. When they disagree, the score lands in the uncertain band, which is the correct behavior for ambiguous cases.

**What it misses:** Non-native English speakers write more uniformly by necessity — limited vocabulary and shorter sentences score as AI-like. Academic and legal writing is structurally regular for legitimate reasons. Haiku and minimalist poetry will score as AI-generated regardless of origin.

**Output:** A float in [0.0, 1.0] where 1.0 = highly uniform / AI-like structure.

---

## Confidence Scoring

### Combination formula

```
confidence = (0.6 × llm_score) + (0.4 × stylometric_score)
```

The LLM signal carries more weight (0.6) because it captures semantic patterns that structural metrics cannot. The stylometric signal (0.4) acts as an independent structural corroboration.

### Thresholds

| Confidence range | Attribution    | Label variant                 |
| ---------------- | -------------- | ----------------------------- |
| ≥ 0.65           | `likely_ai`    | AI-Generated Content Detected |
| 0.36 – 0.64      | `uncertain`    | Origin Uncertain              |
| ≤ 0.35           | `likely_human` | Appears Human-Written         |

The uncertain band is intentionally wide (~29 points) because the spec explicitly identifies false positives (labeling human work as AI) as worse than false negatives. A score must reach 0.65 before the system asserts a confident AI verdict.

### Validation — two example submissions

**High-confidence AI example:**

```
Text: "It is important to note that artificial intelligence represents a
transformative paradigm shift. Furthermore, stakeholders must collaborate
to ensure responsible deployment across various sectors."

llm_score:         0.92
stylometric_score: 0.495
confidence:        0.75
attribution:       likely_ai
```

**High-confidence human example:**

```
Text: "ok so i finally tried that ramen place and honestly? underwhelming.
broth was fine but way too salty, was thirsty for hours after"

llm_score:         0.17
stylometric_score: 0.3856
confidence:        0.2562
attribution:       likely_human
```

The gap between `0.75` and `0.256` across two clearly different inputs confirms the scoring produces meaningful variation rather than clustering near a fixed value.

---

## Transparency Label

Three label variants are returned in the `label` field of `POST /submit` responses based on the confidence score. The exact text each variant displays:

### High-confidence AI (`confidence ≥ 0.65`)

```
⚠️ AI-Generated Content Detected
Our analysis found strong indicators that this content was likely generated
by an AI writing tool rather than written by the credited author. This label
is based on automated detection and may not be perfectly accurate.
If you are the creator and believe this is incorrect, you can submit an
appeal below.
```

### Uncertain (`0.35 < confidence < 0.65`)

```
🔍 Origin Uncertain
Our system could not confidently determine whether this content was written
by a human or generated by AI. This may reflect a genuinely ambiguous writing
style, mixed authorship, or the limits of automated detection.
If you are the creator and want to clarify the origin of your work, you can
submit an appeal below.
```

### High-confidence human (`confidence ≤ 0.35`)

```
✅ Appears Human-Written
Our analysis found no strong indicators of AI-generated content. This label
reflects automated detection only and is not a guarantee of human authorship.
```

**Design rationale:** The AI and uncertain labels both include an explicit appeal prompt because those are the cases where a creator may have been misclassified. The human label is quieter — there is less urgency to appeal a favorable result. The asymmetry is intentional and reflects the spec's guidance that false positives are the higher-stakes error.

---

## Rate Limiting

Rate limiting is applied to `POST /submit` via Flask-Limiter:

```
10 requests per minute
100 requests per day
```

**Reasoning:** A legitimate creator submitting their own work would rarely submit more than a few pieces per session. Ten per minute is generous for normal use while blocking scripted flooding — an adversary trying to enumerate the system's behavior would be throttled after ten rapid requests. One hundred per day allows a prolific creator to submit frequently throughout the day without hitting a ceiling under normal usage.

**Evidence — rate limit test output (12 rapid requests):**

```
Request  1: 200
Request  2: 200
Request  3: 200
Request  4: 200
Request  5: 200
Request  6: 200
Request  7: 200
Request  8: 200
Request  9: 200
Request 10: 200
Request 11: 429
Request 12: 429
```

Requests 11 and 12 return `429 Too Many Requests`, confirming the limit is enforced.

---

## Audit Log

Every attribution decision and appeal is written to `audit_log.json` as a structured entry. Sample entries (3 shown):

```json
[
  {
    "content_id": "3cc395d4-52a4-43d6-82ba-542033df0182",
    "creator_id": "test-ai",
    "timestamp": "2026-06-28T15:40:33.962696+00:00",
    "attribution": "likely_ai",
    "confidence": 0.75,
    "llm_score": 0.92,
    "stylometric_score": 0.495,
    "status": "classified",
    "appeal_reasoning": null,
    "appeal_timestamp": null
  },
  {
    "content_id": "eba34949-ca7a-4cd8-9735-01fc1a4714e3",
    "creator_id": "test-human",
    "timestamp": "2026-06-28T15:41:04.962471+00:00",
    "attribution": "likely_human",
    "confidence": 0.2562,
    "llm_score": 0.17,
    "stylometric_score": 0.3856,
    "status": "classified",
    "appeal_reasoning": null,
    "appeal_timestamp": null
  },
  {
    "content_id": "24dff87a-d563-4c12-be15-c8405047bacd",
    "creator_id": "label-test-human",
    "timestamp": "2026-06-28T16:00:05.228253+00:00",
    "attribution": "likely_human",
    "confidence": 0.2562,
    "llm_score": 0.17,
    "stylometric_score": 0.3856,
    "status": "under_review",
    "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
    "appeal_timestamp": "2026-06-28T16:00:10.576115+00:00"
  }
]
```

The full log is accessible at `GET /log`.

---

## Known Limitations

### 1. Non-native English speakers and constrained writing forms

Writers whose first language is not English tend to produce shorter, simpler sentences with limited vocabulary range. The stylometric signal penalizes both of these properties — low sentence length variance and low TTR both push the score toward AI-like. If the LLM signal also reads the formal register as AI-generated (which it often does for careful, deliberate prose), the combined confidence can push into the uncertain or even `likely_ai` zone for entirely human-written work. This is the system's most significant fairness blind spot. The wide uncertain band and the appeal path are the primary mitigations, but they place the burden on the creator to self-identify and contest.

### 2. Structured poetry and minimalist prose

Haiku, couplets, and other constrained forms have extremely short sentences (low variance) and often intentionally repeat key words (low TTR). The stylometric signal will score these as AI-generated regardless of authorship. The LLM signal may partially compensate if the semantic content is distinctly human, but a three-line haiku gives the model too little text to assess meaningfully. Confidence scores for constrained poetic forms should not be trusted.

---

## Spec Reflection

**One way the spec helped:** Writing the three transparency label variants in `planning.md` before touching any implementation code was the most valuable constraint in the project. Having the exact strings already defined meant the `generate_label` function had a precise target — there was no ambiguity about what "uncertain" should say or where its threshold should be. It also forced the threshold decision (`0.35` / `0.65`) to be made as a design choice rather than a tuning afterthought.

**One way implementation diverged from the spec:** The spec assumed finding a test input that reliably lands in the uncertain band would be straightforward. In practice, the LLM signal is quite decisive — it pushes toward 0.17 or 0.85+ on most natural text, leaving the stylometric signal insufficient on its own to pull the combined score into the `0.35–0.65` range. The uncertain label is reachable, but only with carefully constructed mixed-register text. In a production system this would call for recalibrating signal weights or widening the uncertain band further.

---

## AI Usage

### Instance 1 — Flask app skeleton and Signal 1 function

**Directed:** Provided the detection signals section of `planning.md` and the architecture diagram. Asked the AI tool to generate the Flask app skeleton with a `POST /submit` route stub and a `get_llm_score` function returning a structured JSON score from Groq.

**Produced:** A working skeleton and function. The generated prompt used Python's `.format()` with the example JSON `{"llm_score": 0.82}` unescaped, which caused a `KeyError` on every call because `.format()` tried to interpret `llm_score` as a template variable. The fallback silently returned `0.5` for every submission.

**Revised:** Identified the bug by adding debug prints to trace the exception. Fixed by escaping the example JSON in the prompt string as `{{"llm_score": 0.82}}`. The AI tool did not flag this risk; catching it required understanding how Python string formatting works.

### Instance 2 — Signal 2 and confidence scoring logic

**Directed:** Provided the detection signals section (Signal 2 specifics) and the uncertainty representation section from `planning.md`. Asked for a `get_stylometric_score` function computing sentence length variance and TTR, and a `compute_confidence` function applying the `0.6/0.4` weighted average with the three attribution thresholds.

**Produced:** Both functions matching the spec. Verified against all four test inputs from Milestone 4. The TTR normalization logic required adjustment — the initial normalization assumed a fixed midpoint that did not account for the short texts used in testing. Revised the normalization formula to clamp correctly across varying text lengths.

---

## API Reference

| Endpoint  | Method | Request body                      | Response                                                                             |
| --------- | ------ | --------------------------------- | ------------------------------------------------------------------------------------ |
| `/submit` | POST   | `text`, `creator_id`              | `content_id`, `attribution`, `confidence`, `label`, `llm_score`, `stylometric_score` |
| `/appeal` | POST   | `content_id`, `creator_reasoning` | `confirmed`, `status`, `content_id`                                                  |
| `/log`    | GET    | —                                 | `count`, `entries[]`                                                                 |

---

## Setup

```bash
# Clone and enter repo
git clone https://github.com/YOUR_USERNAME/ai201-project4-provenance-guard.git
cd ai201-project4-provenance-guard

# Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# or: .venv\Scripts\activate    # Windows Command Prompt

# Install dependencies
pip install -r requirements.txt

# Create .env file (never commit this)
echo "GROQ_API_KEY=your_key_here" > .env

# Run the server
python app.py
```

## Requirements

```
flask>=3.0.0
flask-limiter>=3.5.0
groq==0.15.0
python-dotenv==1.0.1
```
