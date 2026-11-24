import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILL_CATALOG = (
    "Python", "Java", "JavaScript", "SQL", "HTML", "CSS", "Flask", "Django",
    "React", "Node.js", "Machine Learning", "Deep Learning", "NLP", "Pandas",
    "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Git", "Docker",
    "AWS", "Azure", "Power BI", "Tableau", "Excel", "Communication",
    "Data Analysis", "C", "C++", "MongoDB", "MySQL", "REST API",
)

LEARNING_LINKS = {
    "Python": "https://docs.python.org/3/tutorial/",
    "SQL": "https://www.mysql.com/",
    "Machine Learning": "https://scikit-learn.org/stable/tutorial/",
    "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
    "React": "https://react.dev/learn",
    "Git": "https://git-scm.com/book/en/v2",
    "Communication": "https://www.coursera.org/learn/wharton-communication-skills",
}


def find_skills(text, catalog=SKILL_CATALOG):
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", text.lower())
    found = []
    for skill in catalog:
        phrase = re.sub(r"[^a-z0-9+#.]+", " ", skill.lower()).strip()
        if re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", normalized):
            found.append(skill)
    return sorted(found, key=str.casefold)


def analyze_resume(text):
    skills = find_skills(text)
    words = re.findall(r"\b[\w+#.]+\b", text)
    sections = {
        "experience": bool(re.search(r"\b(experience|employment|work history|internship)\b", text, re.I)),
        "education": bool(re.search(r"\b(education|degree|university|college)\b", text, re.I)),
        "projects": bool(re.search(r"\b(projects?|portfolio)\b", text, re.I)),
        "contact": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)),
    }
    score = min(100, len(skills) * 7 + sum(sections.values()) * 10 + min(len(words) // 20, 20))
    suggestions = []
    if not sections["contact"]:
        suggestions.append("Add a professional email address to your contact section.")
    for section in ("experience", "projects", "education"):
        if not sections[section]:
            suggestions.append(f"Add a clearly labeled {section} section.")
    if len(skills) < 5:
        suggestions.append("Include relevant technical and transferable skills using the wording in target job descriptions.")
    if len(words) < 150:
        suggestions.append("Add concise details about your projects, impact, and responsibilities.")
    return {
        "score": score,
        "skills": skills,
        "sections": sections,
        "word_count": len(words),
        "suggestions": suggestions,
    }


def match_opportunity(profile_skills, opportunity_skills, profile_text, opportunity_text):
    required = {skill.casefold(): skill for skill in opportunity_skills}
    owned = {skill.casefold() for skill in profile_skills}
    overlap = len(set(required) & owned) / len(required) if required else 0.0
    documents = [profile_text.strip() or "student", opportunity_text.strip() or "opportunity"]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        vectors = vectorizer.fit_transform(documents)
        similarity = float(cosine_similarity(vectors[0:1], vectors[1:2])[0][0])
    except ValueError:
        similarity = 0.0
    score = round((0.7 * overlap + 0.3 * similarity) * 100)
    matched = sorted((required[name] for name in set(required) & owned), key=str.casefold)
    missing = sorted((required[name] for name in set(required) - owned), key=str.casefold)
    return {
        "match_percent": max(0, min(100, score)),
        "matched_skills": matched,
        "missing_skills": missing,
        "explanation": (
            f"{len(matched)} of {len(required)} listed skills match your profile; "
            "the score combines skill overlap (70%) and TF-IDF text similarity (30%)."
        ),
    }


def answer_feedback(answer):
    words = re.findall(r"\b[\w'-]+\b", answer)
    strengths = []
    if len(words) >= 40:
        strengths.append("Your response has enough detail to develop a clear example.")
    if re.search(r"\b(result|improved|increased|reduced|built|led|learned)\b", answer, re.I):
        strengths.append("You mention an action or outcome.")
    if not strengths:
        strengths.append("You have a starting point; add a specific example and what you learned.")
    if len(words) < 40:
        strengths.append("Expand the answer with context, your actions, and the result (STAR structure).")
    return " ".join(strengths) + " This automated feedback checks response structure, not factual correctness."
