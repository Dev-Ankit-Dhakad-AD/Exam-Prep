import json
import sys
from collections import defaultdict
from google import genai
from pydantic import BaseModel
from typing import List, Optional

# Ensure UTF-8 output on Windows consoles for emojis/symbols
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# Configuration & Setup
# =====================================================================
# To keep this basic and explainable, we are using the Gemini API.
# It can read images/PDFs directly (Task 1) and can classify text 
# based on semantic understanding (Task 2) without needing a complex 
# local Machine Learning model that is hard to explain.
try:
    client = genai.Client() # Assumes GEMINI_API_KEY is set in your environment variables
except Exception:
    # Gracefully allow mock demonstrations to run without crashing on startup
    client = None

# =====================================================================
# Data Structures (What our data looks like)
# =====================================================================
class Question(BaseModel):
    text: str
    marks: int
    question_type: str # e.g., "theory", "numerical", "derivation"
    topic: Optional[str] = None # Will be filled in during Task 2

class ExtractedPaper(BaseModel):
    year: int
    questions: List[Question]

class TopicStats(BaseModel):
    topic_name: str
    total_marks: int
    frequency: int
    types_count: dict # e.g., {"theory": 2, "numerical": 1}

# =====================================================================
# Task 1: Extract and clean questions from past papers
# =====================================================================
def extract_questions_from_image(image_path: str, year: int) -> ExtractedPaper:
    """
    Reads an image of a question paper and extracts the questions using AI.
    """
    print(f"Extracting questions from {image_path}...")
    
    # In a real run, you'd upload the file via the SDK, but here's the concept:
    # sample_file = client.files.upload(file=image_path)
    
    prompt = """
    Analyze this exam paper image. Extract all questions.
    For each question, determine the text, the marks assigned, 
    and classify its type as 'theory', 'numerical', or 'derivation'.
    """
    
    # We enforce structured JSON output using Pydantic schemas so the app doesn't break
    ai_client = client or genai.Client()
    response = ai_client.models.generate_content(
        model='gemini-3.8-flash',
        contents=[prompt], # In reality, you'd pass [sample_file, prompt]
        config={
            'response_mime_type': 'application/json',
            'response_schema': ExtractedPaper,
        },
    )
    
    # Parse the structured response
    paper_data = ExtractedPaper.model_validate_json(response.text)
    # Ensure year is set correctly
    paper_data.year = year
    return paper_data

# =====================================================================
# Task 2: Map each question to a syllabus topic
# =====================================================================
def map_topics(paper: ExtractedPaper, syllabus_topics: List[str]) -> ExtractedPaper:
    """
    Assigns each question to the closest matching syllabus topic.
    """
    print("Mapping questions to syllabus topics...")
    
    topics_str = ", ".join(syllabus_topics)
    
    ai_client = client or genai.Client()
    for question in paper.questions:
        prompt = f"""
        Given the following syllabus topics: [{topics_str}]
        
        Question: "{question.text}"
        
        Which ONE syllabus topic does this question best fit into? 
        Return ONLY the exact name of the topic from the list.
        """
        
        response = ai_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt
        )
        
        # Clean the output and assign
        question.topic = response.text.strip()
        
    return paper

# =====================================================================
# Task 3: Compute topic frequency, marks weightage, and trends
# =====================================================================
def compute_statistics(all_papers: List[ExtractedPaper]) -> dict:
    """
    Aggregates the questions to find out which topics are most important.
    """
    print("Computing weightage and trends...")
    stats = defaultdict(lambda: {"marks": 0, "frequency": 0, "types": defaultdict(int)})
    
    for paper in all_papers:
        for q in paper.questions:
            topic = q.topic
            if not topic: continue
            
            stats[topic]["marks"] += q.marks
            stats[topic]["frequency"] += 1
            stats[topic]["types"][q.question_type] += 1
            
    return dict(stats)

# =====================================================================
# Task 4: Output a ranked "study priority" list
# =====================================================================
def generate_study_plan(stats: dict) -> None:
    """
    Ranks the topics based on a simple, explainable formula and prints the plan.
    Formula: Priority Score = (Total Marks) + (Frequency * 5)
    """
    print("\n" + "="*50)
    print("🎯 PRIORITIZED REVISION PLAN 🎯")
    print("="*50)
    
    priorities = []
    for topic, data in stats.items():
        # A very basic, explainable scoring system:
        score = data["marks"] + (data["frequency"] * 5)
        priorities.append({
            "topic": topic, 
            "score": score, 
            "marks": data["marks"], 
            "freq": data["frequency"]
        })
        
    # Sort highest score first
    priorities.sort(key=lambda x: x["score"], reverse=True)
    
    for rank, p in enumerate(priorities, start=1):
        print(f"{rank}. {p['topic']} (Priority Score: {p['score']})")
        print(f"   - Total Marks Historically: {p['marks']}")
        print(f"   - Times Asked: {p['freq']}")
        print()

# =====================================================================
# Main Execution (Mock Data Example)
# =====================================================================
if __name__ == "__main__":
    # 1. Define Syllabus
    syllabus = ["Thermodynamics", "Electromagnetism", "Quantum Mechanics", "Fluid Dynamics"]
    
    # 2. Mocking Task 1 & 2 for demonstration
    # In reality, you'd call extract_questions_from_image("paper_2023.jpg", 2023)
    mock_paper = ExtractedPaper(
        year=2023,
        questions=[
            Question(text="Explain the laws of thermodynamics.", marks=10, question_type="theory", topic="Thermodynamics"),
            Question(text="Calculate the magnetic flux.", marks=5, question_type="numerical", topic="Electromagnetism"),
            Question(text="Derive the Navier-Stokes equation.", marks=15, question_type="derivation", topic="Fluid Dynamics"),
            Question(text="What is entropy?", marks=2, question_type="theory", topic="Thermodynamics")
        ]
    )
    
    # 3. Compute Stats
    stats = compute_statistics([mock_paper])
    
    # 4. Generate Plan
    generate_study_plan(stats)
