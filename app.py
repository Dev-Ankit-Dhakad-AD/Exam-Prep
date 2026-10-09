import sys
import os
import json
import base64
from collections import defaultdict

# ── Load .env file (so GEMINI_API_KEY is picked up automatically) ─────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; can also set env var manually

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ── UTF-8 console output ──────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Gemini Client ─────────────────────────────────────────────────────────────
try:
    from google import genai
    from pydantic import BaseModel
    from typing import List, Optional
    client = genai.Client()
    AI_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Gemini client not available: {e}")
    client = None
    AI_AVAILABLE = False

# ── Pydantic Models ───────────────────────────────────────────────────────────
if AI_AVAILABLE:
    class Question(BaseModel):
        text: str
        marks: int
        question_type: str          # theory | numerical | derivation
        topic: Optional[str] = None

    class ExtractedPaper(BaseModel):
        year: int
        questions: List[Question]

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_FOLDER = "/tmp/uploads" if os.environ.get("VERCEL") else os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory store (per session; replace with DB for production)
store = {
    "papers": [],       # List[ExtractedPaper-like dicts]
    "syllabus": []
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_statistics(papers):
    stats = defaultdict(lambda: {"marks": 0, "frequency": 0, "types": defaultdict(int)})
    for paper in papers:
        for q in paper.get("questions", []):
            topic = q.get("topic")
            if not topic:
                continue
            stats[topic]["marks"]    += q.get("marks", 0)
            stats[topic]["frequency"] += 1
            stats[topic]["types"][q.get("question_type", "unknown")] += 1
    # Convert inner defaultdicts to regular dicts
    return {k: {**v, "types": dict(v["types"])} for k, v in stats.items()}

def generate_priorities(stats):
    priorities = []
    for topic, data in stats.items():
        score = data["marks"] + (data["frequency"] * 5)
        priorities.append({
            "topic":     topic,
            "score":     score,
            "marks":     data["marks"],
            "frequency": data["frequency"],
            "types":     data["types"]
        })
    priorities.sort(key=lambda x: x["score"], reverse=True)
    return priorities

# ── Mock extraction (used when AI unavailable or for demo) ────────────────────
MOCK_QUESTIONS = [
    {"text": "Explain the laws of thermodynamics.", "marks": 10, "question_type": "theory",      "topic": "Thermodynamics"},
    {"text": "Calculate the magnetic flux density.",  "marks": 5,  "question_type": "numerical",   "topic": "Electromagnetism"},
    {"text": "Derive the Navier-Stokes equation.",    "marks": 15, "question_type": "derivation",  "topic": "Fluid Dynamics"},
    {"text": "What is entropy and its significance?", "marks": 2,  "question_type": "theory",      "topic": "Thermodynamics"},
    {"text": "Explain the photoelectric effect.",     "marks": 8,  "question_type": "theory",      "topic": "Quantum Mechanics"},
    {"text": "Numerical on Maxwell's equations.",     "marks": 6,  "question_type": "numerical",   "topic": "Electromagnetism"},
]

def ai_extract(image_path, year, syllabus):
    """Use Gemini to extract questions from uploaded image."""
    if not AI_AVAILABLE or not client:
        raise RuntimeError("AI client not available")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else \
           "image/png"  if ext == ".png" else \
           "application/pdf"

    syllabus_str = ", ".join(syllabus) if syllabus else "Auto-detect topics"

    prompt = f"""Analyze this exam paper image carefully.

Syllabus topics available: [{syllabus_str}]

For EACH question found:
1. Extract the full question text
2. Determine marks allocated  
3. Classify question type as exactly one of: 'theory', 'numerical', 'derivation'
4. Assign it to the best matching syllabus topic from the list provided

Return structured JSON."""

    image_part = {"inline_data": {"data": base64.b64encode(image_bytes).decode(), "mime_type": mime}}

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[image_part, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": ExtractedPaper,
            }
        )
    except Exception as err:
        print(f"[WARN] gemini-3.8-flash failed ({err}), trying gemini-flash-latest...")
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[image_part, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": ExtractedPaper,
            }
        )

    paper = ExtractedPaper.model_validate_json(response.text)
    paper.year = year
    result = {"year": year, "questions": [q.model_dump() for q in paper.questions]}
    return result

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/status")
def status():
    return jsonify({"ai_available": AI_AVAILABLE, "papers": len(store["papers"]), "syllabus": store["syllabus"]})

@app.route("/api/syllabus", methods=["GET", "POST", "DELETE"])
def syllabus():
    if request.method == "GET":
        return jsonify(store["syllabus"])
    if request.method == "POST":
        data = request.json
        topics = data.get("topics", [])
        store["syllabus"] = [t.strip() for t in topics if t.strip()]
        return jsonify({"ok": True, "syllabus": store["syllabus"]})
    if request.method == "DELETE":
        store["syllabus"] = []
        return jsonify({"ok": True})

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f    = request.files["file"]
    year = int(request.form.get("year", 2024))
    use_mock = request.form.get("mock", "false").lower() == "true"

    print(f"[UPLOAD] file={f.filename!r}  year={year}  mock={use_mock}  AI_AVAILABLE={AI_AVAILABLE}")

    if use_mock or not AI_AVAILABLE:
        # Demo mode — return mock data
        import random
        print("[UPLOAD] → Running in DEMO mode (returning mock questions)")
        questions = [dict(q) for q in MOCK_QUESTIONS]
        random.shuffle(questions)
        paper = {"year": year, "questions": questions, "filename": f.filename, "mock": True}
        store["papers"].append(paper)
        return jsonify({"ok": True, "paper": paper, "mock": True})

    # Save file
    filename = f"{year}_{f.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)

    try:
        paper = ai_extract(filepath, year, store["syllabus"])
        paper["filename"] = f.filename
        paper["mock"] = False
        store["papers"].append(paper)
        return jsonify({"ok": True, "paper": paper})
    except Exception as e:
        return jsonify({"error": str(e), "hint": "Set GEMINI_API_KEY env variable or use Demo mode"}), 500

@app.route("/api/papers", methods=["GET", "DELETE"])
def papers():
    if request.method == "GET":
        return jsonify(store["papers"])
    if request.method == "DELETE":
        store["papers"] = []
        return jsonify({"ok": True})

@app.route("/api/analysis")
def analysis():
    if not store["papers"]:
        return jsonify({"error": "No papers uploaded yet"}), 400
    stats      = compute_statistics(store["papers"])
    priorities = generate_priorities(stats)
    total_qs   = sum(len(p.get("questions", [])) for p in store["papers"])
    total_marks = sum(q.get("marks", 0) for p in store["papers"] for q in p.get("questions", []))
    return jsonify({
        "stats":      stats,
        "priorities": priorities,
        "summary": {
            "total_papers": len(store["papers"]),
            "total_questions": total_qs,
            "total_marks": total_marks,
            "topics_covered": len(stats),
        }
    })

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Exam Intelligence Platform running at http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)
