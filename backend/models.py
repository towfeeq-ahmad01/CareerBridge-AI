from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from backend import db

profile_skills = db.Table(
    "profile_skills",
    db.Column("profile_id", db.Integer, db.ForeignKey("student_profiles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)
job_skills = db.Table(
    "job_skills",
    db.Column("job_id", db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)
internship_skills = db.Table(
    "internship_skills",
    db.Column("internship_id", db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    profile = db.relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes = db.relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    applications = db.relationship("Application", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    headline = db.Column(db.String(180), nullable=False, default="")
    education = db.Column(db.String(180), nullable=False, default="")
    location = db.Column(db.String(120), nullable=False, default="")
    bio = db.Column(db.Text, nullable=False, default="")
    user = db.relationship("User", back_populates="profile")
    skills = db.relationship("Skill", secondary=profile_skills, order_by="Skill.name")


class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(255), nullable=False)
    extracted_text = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    analysis_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="resumes")


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    company = db.Column(db.String(160), nullable=False, index=True)
    location = db.Column(db.String(120), nullable=False, default="Remote")
    category = db.Column(db.String(100), nullable=False, default="Technology", index=True)
    description = db.Column(db.Text, nullable=False)
    apply_url = db.Column(db.String(500), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    skills = db.relationship("Skill", secondary=job_skills, order_by="Skill.name")


class Internship(db.Model):
    __tablename__ = "internships"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    company = db.Column(db.String(160), nullable=False, index=True)
    location = db.Column(db.String(120), nullable=False, default="Remote")
    category = db.Column(db.String(100), nullable=False, default="Technology", index=True)
    duration = db.Column(db.String(80), nullable=False, default="12 weeks")
    description = db.Column(db.Text, nullable=False)
    apply_url = db.Column(db.String(500), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    skills = db.relationship("Skill", secondary=internship_skills, order_by="Skill.name")


class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="applied")
    notes = db.Column(db.Text, default="")
    applied_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="applications")
    job = db.relationship("Job")
    internship = db.relationship("Internship")
    __table_args__ = (
        db.CheckConstraint(
            "(job_id IS NOT NULL AND internship_id IS NULL) OR "
            "(job_id IS NULL AND internship_id IS NOT NULL)",
            name="ck_application_one_opportunity",
        ),
    )


class SavedOpportunity(db.Model):
    __tablename__ = "saved_opportunities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), nullable=True, index=True)
    saved_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    job = db.relationship("Job")
    internship = db.relationship("Internship")
    __table_args__ = (
        db.CheckConstraint(
            "(job_id IS NOT NULL AND internship_id IS NULL) OR "
            "(job_id IS NULL AND internship_id IS NOT NULL)",
            name="ck_saved_one_opportunity",
        ),
    )


class Recommendation(db.Model):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), nullable=True, index=True)
    match_percent = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    job = db.relationship("Job")
    internship = db.relationship("Internship")
    __table_args__ = (
        db.CheckConstraint(
            "(job_id IS NOT NULL AND internship_id IS NULL) OR "
            "(job_id IS NULL AND internship_id IS NOT NULL)",
            name="ck_recommendation_one_opportunity",
        ),
    )


class InterviewQuestion(db.Model):
    __tablename__ = "interview_questions"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(30), nullable=False, index=True)
    topic = db.Column(db.String(100), nullable=False, default="General")
    question = db.Column(db.Text, nullable=False)
    guidance = db.Column(db.Text, nullable=False)


class InterviewAttempt(db.Model):
    __tablename__ = "interview_attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    question = db.relationship("InterviewQuestion")


class LearningProgress(db.Model):
    __tablename__ = "learning_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="planned")
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    skill = db.relationship("Skill")
    __table_args__ = (db.UniqueConstraint("user_id", "skill_id", name="uq_learning_user_skill"),)
