from backend import db
from backend.models import InterviewQuestion, Internship, Job, Skill
from models.career_ai import SKILL_CATALOG

JOB_DATA = [
    ("Junior Python Developer", "Northstar Labs", "Remote", "Software", "Build and test Python web services with a small product team.", ["Python", "Flask", "SQL", "Git"]),
    ("Data Analyst", "BrightPath Analytics", "Bengaluru, India", "Data", "Prepare datasets, create dashboards, and communicate analysis to stakeholders.", ["Python", "SQL", "Excel", "Data Analysis", "Power BI"]),
    ("Machine Learning Associate", "OpenField AI", "Hybrid", "AI / ML", "Support supervised learning experiments and evaluate model quality.", ["Python", "Machine Learning", "Scikit-learn", "Pandas", "SQL"]),
]
INTERNSHIP_DATA = [
    ("Software Engineering Intern", "Riverstone Tech", "Remote", "Engineering", "12 weeks", "Contribute to APIs, automated tests, and product features with a mentor.", ["Python", "REST API", "Git", "SQL"]),
    ("Data Science Intern", "InsightWorks", "Pune, India", "Data", "16 weeks", "Explore datasets, build notebooks, and present evidence-based findings.", ["Python", "Pandas", "Machine Learning", "SQL"]),
    ("Frontend Developer Intern", "Pixel Harbor", "Remote", "Engineering", "10 weeks", "Build accessible, responsive interfaces and collaborate on design reviews.", ["JavaScript", "HTML", "CSS", "React", "Communication"]),
]
QUESTION_DATA = [
    ("technical", "Python", "How would you find and handle missing values in a dataset?", "Explain how you inspect missingness, choose a strategy based on context, and validate the effect."),
    ("technical", "SQL", "What is the difference between an INNER JOIN and a LEFT JOIN?", "Describe which rows each join keeps and give a small example."),
    ("technical", "Machine Learning", "How do you evaluate a classifier when the classes are imbalanced?", "Discuss a suitable metric such as precision, recall, F1, or PR-AUC and why accuracy can mislead."),
    ("hr", "Behavioral", "Tell me about a time you had to learn something quickly.", "Use Situation, Task, Action, and Result; describe your contribution and reflection."),
    ("hr", "Behavioral", "What kind of team environment helps you do your best work?", "Be specific, give an example, and connect your preferences to collaboration."),
]


def seed_catalog():
    for name in SKILL_CATALOG:
        if not Skill.query.filter_by(name=name).first():
            db.session.add(Skill(name=name))
    db.session.flush()
    skill_map = {skill.name: skill for skill in Skill.query.all()}

    for title, company, location, category, description, skills in JOB_DATA:
        job = Job.query.filter_by(title=title, company=company).first()
        if not job:
            job = Job(title=title, company=company, location=location, category=category, description=description)
            job.skills = [skill_map[name] for name in skills]
            db.session.add(job)
    for title, company, location, category, duration, description, skills in INTERNSHIP_DATA:
        internship = Internship.query.filter_by(title=title, company=company).first()
        if not internship:
            internship = Internship(
                title=title, company=company, location=location, category=category,
                duration=duration, description=description,
            )
            internship.skills = [skill_map[name] for name in skills]
            db.session.add(internship)
    for category, topic, question, guidance in QUESTION_DATA:
        if not InterviewQuestion.query.filter_by(question=question).first():
            db.session.add(InterviewQuestion(category=category, topic=topic, question=question, guidance=guidance))
    db.session.commit()
