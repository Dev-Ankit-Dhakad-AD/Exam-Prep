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

# Persistent store file
DATA_FILE = os.path.join(os.path.dirname(__file__), "store.json")

store = {
    "papers": [],       # List[ExtractedPaper-like dicts]
    "syllabus": []
}

def load_store():
    global store
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                store["papers"] = loaded.get("papers", [])
                store["syllabus"] = loaded.get("syllabus", [])
                print(f"[STORE] Loaded {len(store['papers'])} paper(s) and {len(store['syllabus'])} topic(s) from {DATA_FILE}")
        except Exception as e:
            print(f"[STORE WARN] Could not load store.json: {e}")

def save_store():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[STORE WARN] Could not save store.json: {e}")

# Load persistent store at startup
load_store()

import re

# ── Helpers ───────────────────────────────────────────────────────────────────
def match_topic_for_question(text, syllabus_topics):
    if not syllabus_topics:
        return "General / Other"

    text_lower = (text or "").lower()

    # Domain keywords and concepts mapped to common engineering topics
    topic_rules = {
        "kmap": ["k-map", "kmap", "karnaugh", "minimal sop", "minimal pos", "5-variable k-map", "min terms", "minterm", "maxterm", "sop expression", "pos expression"],
        "k-map": ["k-map", "kmap", "karnaugh", "minimal sop", "minimal pos", "5-variable k-map", "min terms", "minterm", "maxterm", "sop expression", "pos expression"],
        "flipflop": ["flip-flop", "flipflop", "flip flop", "latch", "latches", "s-r flip", "j-k flip", "race around", "triggering levels", "master slave", "forbidden"],
        "flip-flop": ["flip-flop", "flipflop", "flip flop", "latch", "latches", "s-r flip", "j-k flip", "race around", "triggering levels", "master slave", "forbidden"],
        "counter": ["johnson counter", "jhonson counter", "down counter", "up counter", "synchronous counter", "ripple counter", "ring counter", "count- table", "mod-"],
        "counters": ["johnson counter", "jhonson counter", "down counter", "up counter", "synchronous counter", "ripple counter", "ring counter", "count- table", "mod-"],
        "register": ["shift register", "parallel-in serial-out", "serial-in", "piso", "sipo", "siso", "pipo", "right-shift register"],
        "registers": ["shift register", "parallel-in serial-out", "serial-in", "piso", "sipo", "siso", "pipo", "right-shift register"],
        "multiplexer": ["multiplexer", "mux", "demultiplexer", "demux", "encoder", "decoder", "8:1 mux", "4:1 mux", "multiplexer tree"],
        "mux": ["multiplexer", "mux", "demultiplexer", "demux", "encoder", "decoder", "8:1 mux", "4:1 mux"],
        "logic gates": ["universal gate", "universal gates", "nand gate", "nor gate", "logic functions from universal", "parity generator", "full adder", "half-adder", "totem pole ttl"],
        "gates": ["universal gate", "universal gates", "nand gate", "nor gate", "logic gate"],
        "logic families": ["totem pole", "ttl", "cmos", "logic families", "ttl circuit", "totem pole ttl"],
        "number systems": ["2's complement", "1's complement", "gray code", "hexadecimal", "binary number", "decimal number system", "subtract ("],
        "fourier transform": ["fourier series", "fourier transform", "discrete time fourier", "dtft", "dft", "fft", "frequency domain", "fourier"],
        "signals": ["continuous-time signal", "discrete-time", "convolution", "x[n]", "h[n]", "lti system", "impulse delta", "delta(t)", "signals", "signal x(t)"],
        "rlc": ["resistor, inductor and capacitor", "initial conditions as applicable to resistor", "di/dt", "dv/dt", "switch is closed at t=0", "transient", "impedance", "rlc"],
        "resistor": ["resistor", "registor", "resistance", "ohm", "voltage divider"],
        "registor": ["resistor", "registor", "resistance", "ohm", "voltage divider"],
        "thermodynamics": ["heat", "entropy", "carnot", "temperature", "kelvin", "isothermal", "adiabatic", "enthalpy", "thermal", "refrigeration"],
        "electromagnetism": ["magnetic", "flux", "maxwell", "electric", "gauss", "faraday", "induction", "charge", "lorentz", "solenoid", "dielectric"],
        "fluid dynamics": ["navier", "stokes", "bernoulli", "viscosity", "fluid", "reynolds", "laminar", "turbulent", "pipe", "flow", "boundary layer"],
        "quantum mechanics": ["photoelectric", "schrodinger", "wavefunction", "planck", "quantum", "heisenberg", "bohr", "photon", "compton", "tunneling"],
        "classical mechanics": ["newton", "momentum", "lagrangian", "hamiltonian", "torque", "inertia", "collision", "gravity", "friction", "kinematics"],
        "optics": ["lens", "refraction", "diffraction", "interference", "prism", "polarization", "focal", "laser", "mirror", "wavelength", "dispersion"],
        "data structures": ["tree", "graph", "linked list", "stack", "queue", "binary search", "array", "hashing", "heap", "sorting", "algorithm"],
        "database management": ["sql", "acid", "relational", "normalization", "b-tree", "transaction", "schema", "foreign key", "er model", "deadlock"],
        "computer networks": ["tcp", "ip", "osi", "routing", "packet", "ethernet", "udp", "socket", "dns", "http", "subnet", "firewall"]
    }

    matched_scores = {}
    for topic in syllabus_topics:
        t_clean = topic.strip().lower()
        score = 0

        # Exact substring match of topic name
        if len(t_clean) >= 4 and t_clean in text_lower:
            score += 20

        # Keyword mapping rules
        for rule_key, keywords in topic_rules.items():
            if rule_key == t_clean or rule_key in t_clean or t_clean in rule_key:
                for kw in keywords:
                    if kw in text_lower:
                        score += 15
                        break

        # Token overlap check (min 4 characters)
        t_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', t_clean))
        q_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', text_lower))
        overlap = len(t_tokens.intersection(q_tokens))
        if overlap > 0:
            score += (overlap * 5)

        if score > 0:
            matched_scores[topic] = score

    if matched_scores:
        # Return topic with the highest score
        return max(matched_scores.items(), key=lambda x: x[1])[0]

    # If no syllabus topic matches with confidence, DO NOT force into first topic
    return "General / Other"

def remap_papers_to_syllabus(papers, syllabus):
    if not papers:
        return

    all_questions = []
    for paper in papers:
        for q in paper.get("questions", []):
            all_questions.append(q)

    if not all_questions:
        return

    if not syllabus:
        for q in all_questions:
            q["topic"] = "General / Other"
        save_store()
        return

    # 1. Try Gemini AI Batch Classification with strict precision
    ai_success = False
    if AI_AVAILABLE and client:
        try:
            q_list = "\n".join([f"{i+1}. {q.get('text', '')}" for i, q in enumerate(all_questions)])
            prompt = f"""You are an academic exam syllabus classifier.
We have an exam syllabus with these specific topics:
{json.dumps(syllabus)}

Classify EACH of the questions below.
STRICT RULES:
1. ONLY assign a question to a topic from the syllabus list if the question genuinely covers that topic or its direct sub-concepts.
2. If a question is NOT about any of the listed syllabus topics (e.g. question is about K-Maps, Counters, or Fourier Transform, but the syllabus only has Flip-Flops and Resistors), you MUST label it as "General / Other".
3. NEVER force an unrelated question into any syllabus topic.

Questions:
{q_list}

Return ONLY a valid JSON array of strings containing the topic name or "General / Other" for each question in sequential order."""

            models_to_try = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
            for m in models_to_try:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    assigned = json.loads(resp.text)
                    if isinstance(assigned, list) and len(assigned) == len(all_questions):
                        for idx, topic_name in enumerate(assigned):
                            t_str = str(topic_name).strip()
                            matched_s = next((s for s in syllabus if s.strip().lower() == t_str.lower()), None)
                            all_questions[idx]["topic"] = matched_s if matched_s else ("General / Other" if t_str.lower() in ["general / other", "general", "other"] else match_topic_for_question(all_questions[idx].get("text", ""), syllabus))
                        print("[AI] Successfully batch-remapped all questions with Gemini with strict precision!")
                        ai_success = True
                        break
                except Exception as m_err:
                    print(f"[AI WARN] {m} failed during remap: {m_err}")
        except Exception as e:
            print(f"[AI] Error during batch remap: {e}")

    # 2. Fallback to precise rule-based matcher if AI was offline / quota limit
    if not ai_success:
        for q in all_questions:
            q["topic"] = match_topic_for_question(q.get("text", ""), syllabus)

    # Save changes to persistent store
    save_store()

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

def generate_priorities(stats, syllabus=None):
    priorities = []
    syllabus_lower = [s.strip().lower() for s in (syllabus or [])]
    for topic, data in stats.items():
        is_syllabus = topic.lower() in syllabus_lower
        score = data["marks"] + (data["frequency"] * 5)
        priorities.append({
            "topic":       topic,
            "score":       score,
            "marks":       data["marks"],
            "frequency":   data["frequency"],
            "types":       data["types"],
            "is_syllabus": is_syllabus
        })
    # Syllabus topics ranked first by score, then other/unassigned topics
    priorities.sort(key=lambda x: (1 if x["is_syllabus"] else 0, x["score"]), reverse=True)
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

    models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
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
        save_store()
        return jsonify({
            "ok": True,
            "syllabus": store["syllabus"],
            "papers_remapped": len(store["papers"])
        })
    if request.method == "DELETE":
        store["syllabus"] = []
        save_store()
        return jsonify({"ok": True})

@app.route("/api/papers/remap", methods=["POST"])
def remap_papers():
    if not store["papers"]:
        return jsonify({"ok": True, "message": "No papers uploaded yet", "papers_remapped": 0})
    remap_papers_to_syllabus(store["papers"], store["syllabus"])
    save_store()
    return jsonify({"ok": True, "message": f"Remapped {len(store['papers'])} paper(s) to current syllabus", "papers_remapped": len(store["papers"])})

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
            save_store()
            return jsonify({"ok": True, "syllabus": store["syllabus"]})
    return jsonify({"error": "Question not found"}), 404

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f    = request.files["file"]
    if f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "PDF upload is coming soon! Please upload PNG or JPG exam paper photos for now."}), 400

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
        save_store()
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
        save_store()
        return jsonify({"ok": True, "paper": paper})
    except Exception as e:
        return jsonify({"error": str(e), "hint": "Set GEMINI_API_KEY env variable or use Demo mode"}), 500

@app.route("/api/papers", methods=["GET", "DELETE"])
def papers():
    if request.method == "GET":
        return jsonify(store["papers"])
    if request.method == "DELETE":
        store["papers"] = []
        save_store()
        return jsonify({"ok": True})

@app.route("/api/analysis")
def analysis():
    if not store["papers"]:
        return jsonify({"error": "No papers uploaded yet"}), 400
    stats      = compute_statistics(store["papers"], store["syllabus"])
    priorities = generate_priorities(stats, store["syllabus"])
    total_qs   = sum(len(p.get("questions", [])) for p in store["papers"])
    total_marks = sum(q.get("marks", 0) for p in store["papers"] for q in p.get("questions", []))
    syllabus_lower = [s.strip().lower() for s in store["syllabus"]]
    topics_covered = sum(1 for k, v in stats.items() if k.lower() in syllabus_lower and v["frequency"] > 0)
    return jsonify({
        "stats":      stats,
        "priorities": priorities,
        "summary": {
            "total_papers": len(store["papers"]),
            "total_questions": total_qs,
            "total_marks": total_marks,
            "topics_covered": topics_covered,
            "syllabus_total": len(store["syllabus"])
        }
    })

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Exam Intelligence Platform running at http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)
