# 🎓 ExamPrep — AI Exam Intelligence & Syllabus Priority Platform

An intelligent, full-stack academic examination analysis platform that uses **Multimodal AI Vision (Google Gemini)** to extract exam papers, map questions against target curriculum syllabi, and compute **Study Priority Rankings & Marks Weightage**.

Designed for university students, educators, and curriculum developers to pinpoint high-yield exam topics and optimize study schedules.

---

## 🌟 Key Features

### 1. 👁️ Multimodal Question Paper Extraction
- Accepts scanned exam paper images (`PNG`, `JPG`) and `PDF` documents.
- Uses **Google Gemini Vision (`gemini-3.5-flash` / `gemini-3.8-flash`)** to extract full question text, marks distribution, and question classification (`theory`, `numerical`, `derivation`).
- Built-in **Sample Test Mode (Mock)** for testing offline or without an API key.

### 2. 🎯 Dynamic Syllabus & Topic Alignment
- **Zero Re-upload Workflow**: Add or modify syllabus topics at any time without having to re-upload previously processed papers.
- **Strict, High-Precision Classification**:
  - Leverages academic engineering ontologies (Signals & Systems, Digital Electronics, Circuit Analysis, etc.).
  - Distinguishes specific topics without false positives. Unrelated questions are safely categorized as `General / Other` rather than forced into an arbitrary topic.
- **Manual Overrides**: Inline dropdown on each question card allows instant re-mapping of individual questions.

### 3. 📊 Topic Weightage & Study Priority Algorithm
- Automatically calculates cumulative marks, question frequency, and type breakdown.
- **Priority Scoring Formula**:
  $$\text{Priority Score} = \text{Cumulative Marks} + (\text{Frequency} \times 5)$$
- Generates a prioritized study table highlighting the highest-return exam topics.

### 4. 📈 Interactive Analytics Dashboard
- **Key Performance Indicators (KPIs)**: Papers Analyzed, Questions Identified, Total Marks, Syllabus Topics Covered.
- **Chart.js Visualizations**:
  - Marks Weightage by Topic (Bar Chart)
  - Question Frequency Distribution (Bar Chart)
  - Question Type Breakdown (Donut Chart)
  - Topic Coverage Profile (Radar Chart)

### 5. 🔍 Questions Explorer with Real-Time Search
- Real-time search bar to filter questions by keywords or text.
- Filter dropdowns for syllabus topics and question types (`theory`, `numerical`, `derivation`).

### 6. 📱 Mobile & Tablet Responsive Architecture
- Clean, modern SaaS aesthetic with typography powered by *Plus Jakarta Sans*.
- Fully responsive layout with mobile touch targets, horizontal scroll indicators for tables, and a rich multi-column footer.
- Local file persistence via `store.json` ensuring sessions survive server restarts.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.10+, Flask, Flask-CORS, Pydantic, python-dotenv |
| **AI / Vision** | Google GenAI SDK (`google-genai`), Gemini 3.5 Flash / Gemini 3.8 Flash |
| **Frontend** | Vanilla HTML5, Modern Vanilla CSS (SaaS theme), Vanilla JavaScript (ES6+) |
| **Data Visualization** | Chart.js |
| **Data Persistence** | File-backed JSON store (`store.json`) with in-memory caching |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10 or higher installed.
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/).

### 1. Clone the Repository
```bash
git clone <repository-url>
cd "technical task 2026"
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Start the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://localhost:5000
```

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | Returns backend health, AI engine status, syllabus topics, and paper count. |
| `POST` | `/api/upload` | Uploads an exam paper image/PDF (`file`, `year`, `mock`). Extracts questions. |
| `GET` | `/api/papers` | Retrieves all loaded question papers and questions. |
| `DELETE` | `/api/papers` | Clears all stored exam papers. |
| `POST` | `/api/papers/remap` | Re-evaluates all papers against current syllabus topics. |
| `GET` | `/api/syllabus` | Returns the active syllabus topic list. |
| `POST` | `/api/syllabus` | Updates the syllabus topics and automatically re-maps loaded papers. |
| `DELETE` | `/api/syllabus` | Clears all syllabus topics. |
| `POST` | `/api/questions/update-topic` | Manually updates the topic of a specific question. |
| `GET` | `/api/analysis` | Computes statistics, priority scores, and KPI summary data. |

---

## 📂 Project Structure

```
├── app.py                  # Flask backend server, Gemini integration, and classification logic
├── exam_assistant.py       # Supporting exam assistant utility routines
├── requirements.txt        # Python package dependencies
├── store.json              # Persistent data store (papers, syllabus, extracted questions)
├── .env                    # Environment configuration (GEMINI_API_KEY)
├── uploads/                # Directory storing uploaded paper images & PDFs
├── static/
│   ├── index.html          # Main application user interface
│   ├── style.css           # Modern SaaS styling & responsive layout
│   └── app.js              # Frontend client application logic, API calls, Chart.js rendering
└── Exam Prep/              # Git-tracked project mirror repository
```

---

## 👨‍💻 Developer & Credits
- **Institute**: Institute of Engineering & Technology, Devi Ahilya Vishwavidyalaya (IET DAVV), Indore
- **Department**: Information Technology
- **License**: MIT
