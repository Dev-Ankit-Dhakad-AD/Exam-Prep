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

import re

# ── Helpers ───────────────────────────────────────────────────────────────────
def match_topic_for_question(text, syllabus_topics, current_topic=None):
    if not syllabus_topics:
        return current_topic or "General"

    # 1. Exact or case-insensitive match with existing topic if still in syllabus
    for t in syllabus_topics:
        if current_topic and current_topic.strip().lower() == t.strip().lower():
            return t

    text_lower = (text or "").lower()

    # 2. Substring match of full topic name in question text (longest match first)
    sorted_topics = sorted(syllabus_topics, key=lambda x: len(x), reverse=True)
    for t in sorted_topics:
        t_clean = t.strip().lower()
        if len(t_clean) >= 3 and t_clean in text_lower:
            return t

    # 3. Token / keyword overlap
    q_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', text_lower))
    best_topic = None
    best_overlap = 0
    for t in syllabus_topics:
        t_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', t.lower()))
        overlap = len(q_tokens.intersection(t_tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best_topic = t
    if best_topic and best_overlap > 0:
        return best_topic

    # 4. Domain synonyms for engineering / sciences
    topic_synonyms = {
        "thermodynamics": ["heat", "entropy", "carnot", "temperature", "kelvin", "isothermal", "adiabatic", "enthalpy", "thermal", "refrigeration"],
        "electromagnetism": ["magnetic", "flux", "maxwell", "electric", "gauss", "faraday", "induction", "charge", "lorentz", "solenoid", "dielectric"],
        "fluid dynamics": ["navier", "stokes", "bernoulli", "viscosity", "fluid", "reynolds", "laminar", "turbulent", "pipe", "flow", "boundary layer"],
        "quantum mechanics": ["photoelectric", "schrodinger", "wavefunction", "planck", "quantum", "heisenberg", "bohr", "photon", "compton", "tunneling"],
        "classical mechanics": ["newton", "momentum", "lagrangian", "hamiltonian", "torque", "inertia", "collision", "gravity", "friction", "kinematics"],
        "optics": ["lens", "refraction", "diffraction", "interference", "prism", "polarization", "focal", "laser", "mirror", "wavelength", "dispersion"],
        "digital electronics": ["k-map", "boolean", "logic gate", "flip-flop", "multiplexer", "binary", "counter", "decoder", "karnaugh", "combinational"],
        "data structures": ["tree", "graph", "linked list", "stack", "queue", "binary search", "array", "hashing", "heap", "sorting", "algorithm"],
        "database management": ["sql", "acid", "relational", "normalization", "b-tree", "transaction", "schema", "foreign key", "er model", "deadlock"],
        "computer networks": ["tcp", "ip", "osi", "routing", "packet", "ethernet", "udp", "socket", "dns", "http", "subnet", "firewall"]
    }
    for t in syllabus_topics:
        t_key = t.strip().lower()
        for syn_key, syn_words in topic_synonyms.items():
            if syn_key in t_key or t_key in syn_key:
                for word in syn_words:
                    if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
                        return t

    # 5. Partial match with previous topic
    if current_topic:
        for t in syllabus_topics:
            if current_topic.lower() in t.lower() or t.lower() in current_topic.lower():
                return t

    # 6. Default fallback to first syllabus topic or General
    return syllabus_topics[0] if syllabus_topics else "General"

def remap_papers_to_syllabus(papers, syllabus):
    if not papers or not syllabus:
        return
    for paper in papers:
        for q in paper.get("questions", []):
            new_t = match_topic_for_question(q.get("text", ""), syllabus, q.get("topic"))
            q["topic"] = new_t

def compute_statistics(papers, syllabus=None):
    stats = defaultdict(lambda: {"marks": 0, "frequency": 0, "types": defaultdict(int)})
    # Pre-seed with all current syllabus topics so 0-frequency topics show up
    if syllabus:
        for t in syllabus:
            if t.strip():
                _ = stats[t.strip()]

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

    models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    response = None
    last_err = None

    for m in models_to_try:
        try:
            print(f"[AI] Trying model: {m}...")
            response = client.models.generate_content(
                model=m,
                contents=[image_part, prompt],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ExtractedPaper,
                }
            )
            print(f"[AI] Successfully extracted using {m}!")
            break
        except Exception as err:
            print(f"[WARN] {m} failed ({err}), falling back to next model...")
            last_err = err

    if not response:
        raise RuntimeError(f"All AI models are currently busy or unavailable. Last error: {last_err}")

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
        data = request.json or {}
        topics = data.get("topics", [])
        store["syllabus"] = [t.strip() for t in topics if t.strip()]
        # Immediately re-map all questions in uploaded papers to current syllabus!
        if store["papers"] and store["syllabus"]:
            remap_papers_to_syllabus(store["papers"], store["syllabus"])
        return jsonify({
            "ok": True,
            "syllabus": store["syllabus"],
            "papers_remapped": len(store["papers"])
        })
    if request.method == "DELETE":
        store["syllabus"] = []
        return jsonify({"ok": True})

@app.route("/api/papers/remap", methods=["POST"])
def remap_papers():
    if not store["papers"]:
        return jsonify({"error": "No papers uploaded yet"}), 400
    remap_papers_to_syllabus(store["papers"], store["syllabus"])
    return jsonify({"ok": True, "message": f"Remapped {len(store['papers'])} paper(s) to current syllabus"})

@app.route("/api/questions/update-topic", methods=["POST"])
def update_question_topic():
    data = request.json or {}
    paper_idx = int(data.get("paper_idx", 0))
    q_idx = int(data.get("question_idx", 0))
    new_topic = data.get("topic", "").strip()
    if not new_topic:
        return jsonify({"error": "Topic required"}), 400

    if 0 <= paper_idx < len(store["papers"]):
        paper = store["papers"][paper_idx]
        if 0 <= q_idx < len(paper.get("questions", [])):
            paper["questions"][q_idx]["topic"] = new_topic
            if new_topic not in store["syllabus"]:
                store["syllabus"].append(new_topic)
            return jsonify({"ok": True, "syllabus": store["syllabus"]})
    return jsonify({"error": "Question not found"}), 404

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
        if store["syllabus"]:
            remap_papers_to_syllabus([paper], store["syllabus"])
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
        if store["syllabus"]:
            remap_papers_to_syllabus([paper], store["syllabus"])
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
    stats      = compute_statistics(store["papers"], store["syllabus"])
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
            "topics_covered": sum(1 for v in stats.values() if v["frequency"] > 0),
            "syllabus_total": len(store["syllabus"])
        }
    })

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Exam Intelligence Platform running at http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)
