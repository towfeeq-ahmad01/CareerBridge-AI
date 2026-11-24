import os
import re
import secrets
from collections import Counter
from io import BytesIO
from urllib.parse import urlsplit

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from backend import db
from backend.models import (
    Application, InterviewAttempt, InterviewQuestion, Internship, Job,
    LearningProgress, Recommendation, Resume, SavedOpportunity, Skill,
    StudentProfile, User,
)
from models.career_ai import (
    LEARNING_LINKS, SKILL_CATALOG, analyze_resume, answer_feedback,
    find_skills, match_opportunity,
)

main = Blueprint("main", __name__)
APPLICATION_STATUSES = {"applied", "screening", "interview", "offer", "rejected", "withdrawn"}


@main.before_app_request
def protect_state_changes():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    expected = session.get("_csrf_token")
    supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        if request.path.startswith("/api/"):
            return jsonify(error="Invalid or missing CSRF token."), 400
        abort(400, description="Your form session expired. Reload the page and try again.")


@main.app_context_processor
def inject_template_helpers():
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]

    return {"csrf_token": csrf_token}


def profile_for(user):
    if user.profile is None:
        user.profile = StudentProfile()
        db.session.flush()
    return user.profile


def clean_text(value, max_length=4000):
    return value.strip()[:max_length] if isinstance(value, str) else ""


def request_json_object():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def local_return_path(value):
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc != request.host:
        return None
    if not parsed.path.startswith("/") or "\\" in parsed.path:
        return None
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def rotate_csrf_token():
    session.pop("_csrf_token", None)


def opportunity_skills(opportunity):
    return [skill.name for skill in opportunity.skills]


def profile_skill_names(user):
    return [skill.name for skill in user.profile.skills] if user.profile else []


def get_match(user, opportunity):
    profile = user.profile
    profile_text = " ".join(
        [profile.headline or "", profile.education or "", profile.bio or ""]
        + profile_skill_names(user)
    ) if profile else " ".join(profile_skill_names(user))
    description = f"{opportunity.title} {opportunity.category} {opportunity.description}"
    return match_opportunity(
        profile_skill_names(user), opportunity_skills(opportunity), profile_text, description
    )


def opportunity_card(opportunity, kind, user=None):
    saved = False
    match = None
    if user and user.is_authenticated:
        match = get_match(user, opportunity)
        saved = SavedOpportunity.query.filter_by(
            user_id=user.id,
            job_id=opportunity.id if kind == "job" else None,
            internship_id=opportunity.id if kind == "internship" else None,
        ).first() is not None
    return {"item": opportunity, "kind": kind, "match": match, "saved": saved}


def resolve_opportunity(kind, opportunity_id):
    model = Job if kind == "job" else Internship
    item = db.session.get(model, opportunity_id)
    if item is None or not item.active:
        abort(404)
    return item


def serialize_opportunity(item, kind, user=None):
    data = {
        "id": item.id,
        "type": kind,
        "title": item.title,
        "company": item.company,
        "location": item.location,
        "category": item.category,
        "description": item.description,
        "skills": opportunity_skills(item),
    }
    if kind == "internship":
        data["duration"] = item.duration
    if user:
        data["match"] = get_match(user, item)
    return data


@main.route("/")
def home():
    jobs = Job.query.filter_by(active=True).order_by(Job.created_at.desc()).limit(3).all()
    internships = Internship.query.filter_by(active=True).order_by(Internship.created_at.desc()).limit(3).all()
    return render_template("home.html", jobs=jobs, internships=internships)


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        name = clean_text(request.form.get("full_name"), 120)
        email = clean_text(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter your name and a valid email address.", "danger")
        elif not 10 <= len(password) <= 256:
            flash("Use a password between 10 and 256 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
        else:
            user = User(email=email, full_name=name, role="student")
            user.set_password(password)
            user.profile = StudentProfile()
            db.session.add(user)
            db.session.commit()
            login_user(user)
            rotate_csrf_token()
            flash("Welcome to CareerBridge AI. Complete your profile to get better matches.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth.html", mode="register")


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = clean_text(request.form.get("email"), 255).lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first() if len(password) <= 256 else None
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            rotate_csrf_token()
            flash("You are signed in.", "success")
            return redirect(local_return_path(request.args.get("next")) or url_for("main.dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("auth.html", mode="login")


@main.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    rotate_csrf_token()
    flash("You have signed out.", "info")
    return redirect(url_for("main.home"))


@main.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    profile = profile_for(current_user)
    if request.method == "POST":
        profile.headline = clean_text(request.form.get("headline"), 180)
        profile.education = clean_text(request.form.get("education"), 180)
        profile.location = clean_text(request.form.get("location"), 120)
        profile.bio = clean_text(request.form.get("bio"), 1500)
        selected = {
            name.casefold(): name
            for name in request.form.getlist("skills")
            if name in SKILL_CATALOG
        }
        profile.skills = Skill.query.filter(Skill.name.in_(selected.values())).order_by(Skill.name).all() if selected else []
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("main.dashboard"))

    jobs = Job.query.filter_by(active=True).all()
    internships = Internship.query.filter_by(active=True).all()
    recommendations = []
    for kind, items in (("job", jobs), ("internship", internships)):
        for item in items:
            recommendations.append(opportunity_card(item, kind, current_user))
    recommendations.sort(key=lambda card: card["match"]["match_percent"], reverse=True)
    recent_applications = Application.query.filter_by(user_id=current_user.id).order_by(
        Application.applied_at.desc()
    ).limit(5).all()
    resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).first()
    return render_template(
        "dashboard.html", profile=profile, skill_catalog=SKILL_CATALOG,
        recommendations=recommendations[:4], applications=recent_applications,
        resume=resume, saved_count=SavedOpportunity.query.filter_by(user_id=current_user.id).count(),
    )


@main.route("/resume", methods=["GET", "POST"])
@login_required
def resume_analyzer():
    if request.method == "POST":
        upload = request.files.get("resume")
        if not upload or not upload.filename:
            flash("Choose a PDF resume to upload.", "warning")
            return redirect(url_for("main.resume_analyzer"))
        filename = secure_filename(upload.filename)
        if not filename or not filename.lower().endswith(".pdf"):
            flash("Only PDF resumes are supported.", "danger")
            return redirect(url_for("main.resume_analyzer"))
        raw = upload.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
        if len(raw) > current_app.config["MAX_CONTENT_LENGTH"]:
            flash("The PDF exceeds the 5 MB upload limit.", "danger")
            return redirect(url_for("main.resume_analyzer"))
        try:
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted:
                flash("This PDF is password-protected. Upload an unlocked copy.", "danger")
                return redirect(url_for("main.resume_analyzer"))
            if len(reader.pages) > 30:
                flash("The PDF has more than 30 pages. Upload a shorter resume.", "danger")
                return redirect(url_for("main.resume_analyzer"))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except (PdfReadError, ValueError, EOFError) as error:
            current_app.logger.info("Rejected invalid PDF resume: %s", error)
            flash("Could not read this PDF. Upload a valid, text-based PDF.", "danger")
            return redirect(url_for("main.resume_analyzer"))
        if not text:
            flash("No selectable text was found. Upload a text-based PDF rather than a scanned image.", "warning")
            return redirect(url_for("main.resume_analyzer"))
        analysis = analyze_resume(text)
        stored_name = f"{current_user.id}_{secrets.token_hex(8)}_{filename}"
        upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
        with open(upload_path, "wb") as resume_file:
            resume_file.write(raw)
        resume = Resume(
            user_id=current_user.id,
            filename=filename,
            storage_key=stored_name,
            extracted_text=text[:50000],
            score=analysis["score"],
            analysis_json=analysis,
        )
        db.session.add(resume)
        profile = profile_for(current_user)
        known = {skill.name.casefold() for skill in profile.skills}
        new_skills = [name for name in analysis["skills"] if name.casefold() not in known]
        if new_skills:
            profile.skills.extend(Skill.query.filter(Skill.name.in_(new_skills)).all())
        db.session.commit()
        flash("Resume analyzed. Detected skills were added to your profile.", "success")
        return redirect(url_for("main.resume_analyzer"))
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).all()
    return render_template("resume.html", resumes=resumes)


@main.route("/jobs")
def jobs():
    query = clean_text(request.args.get("q"), 120)
    category = clean_text(request.args.get("category"), 100)
    listing = Job.query.filter_by(active=True)
    if query:
        term = f"%{query}%"
        listing = listing.filter(or_(Job.title.ilike(term), Job.company.ilike(term), Job.description.ilike(term)))
    if category:
        listing = listing.filter(Job.category == category)
    items = listing.order_by(Job.created_at.desc()).all()
    categories = [row[0] for row in db.session.query(Job.category).filter_by(active=True).distinct().order_by(Job.category).all()]
    cards = [opportunity_card(item, "job", current_user) for item in items]
    return render_template("opportunities.html", kind="job", cards=cards, categories=categories, query=query, category=category)


@main.route("/internships")
def internships():
    query = clean_text(request.args.get("q"), 120)
    category = clean_text(request.args.get("category"), 100)
    listing = Internship.query.filter_by(active=True)
    if query:
        term = f"%{query}%"
        listing = listing.filter(or_(Internship.title.ilike(term), Internship.company.ilike(term), Internship.description.ilike(term)))
    if category:
        listing = listing.filter(Internship.category == category)
    items = listing.order_by(Internship.created_at.desc()).all()
    categories = [row[0] for row in db.session.query(Internship.category).filter_by(active=True).distinct().order_by(Internship.category).all()]
    cards = [opportunity_card(item, "internship", current_user) for item in items]
    return render_template("opportunities.html", kind="internship", cards=cards, categories=categories, query=query, category=category)


@main.route("/opportunity/<kind>/<int:opportunity_id>")
def opportunity_detail(kind, opportunity_id):
    if kind not in {"job", "internship"}:
        abort(404)
    item = resolve_opportunity(kind, opportunity_id)
    card = opportunity_card(item, kind, current_user)
    application = None
    saved = False
    if current_user.is_authenticated:
        lookup = {"user_id": current_user.id, "job_id": item.id if kind == "job" else None, "internship_id": item.id if kind == "internship" else None}
        application = Application.query.filter_by(**lookup).first()
        saved = SavedOpportunity.query.filter_by(**lookup).first() is not None
    return render_template("opportunity_detail.html", card=card, application=application, saved=saved)


@main.route("/opportunity/<kind>/<int:opportunity_id>/save", methods=["POST"])
@login_required
def save_opportunity(kind, opportunity_id):
    item = resolve_opportunity(kind, opportunity_id)
    values = {"user_id": current_user.id, "job_id": item.id if kind == "job" else None, "internship_id": item.id if kind == "internship" else None}
    existing = SavedOpportunity.query.filter_by(**values).first()
    if existing:
        db.session.delete(existing)
        flash("Opportunity removed from saved items.", "info")
    else:
        db.session.add(SavedOpportunity(**values))
        flash("Opportunity saved.", "success")
    db.session.commit()
    return redirect(local_return_path(request.referrer) or url_for("main.opportunity_detail", kind=kind, opportunity_id=item.id))


@main.route("/opportunity/<kind>/<int:opportunity_id>/apply", methods=["POST"])
@login_required
def apply_opportunity(kind, opportunity_id):
    item = resolve_opportunity(kind, opportunity_id)
    values = {"user_id": current_user.id, "job_id": item.id if kind == "job" else None, "internship_id": item.id if kind == "internship" else None}
    application = Application.query.filter_by(**values).first()
    if application:
        flash("You already track an application for this opportunity.", "info")
    else:
        db.session.add(Application(**values, status="applied"))
        db.session.commit()
        flash("Application added to your tracker.", "success")
    return redirect(url_for("main.applications"))


@main.route("/skills", methods=["GET", "POST"])
@login_required
def skills():
    profile = profile_for(current_user)
    comparison = None
    if request.method == "POST":
        required_text = clean_text(request.form.get("required_skills"), 2000)
        required = find_skills(required_text)
        owned = {skill.name.casefold() for skill in profile.skills}
        missing = [skill for skill in required if skill.casefold() not in owned]
        matched = [skill for skill in required if skill.casefold() in owned]
        comparison = {"required": required, "missing": missing, "matched": matched}
        session["last_skill_gap"] = comparison
    return render_template("skills.html", profile=profile, comparison=comparison, suggested=SKILL_CATALOG)


@main.route("/roadmap", methods=["GET", "POST"])
@login_required
def roadmap():
    if request.method == "POST":
        skill_id = request.form.get("skill_id", type=int)
        status = request.form.get("status", "")
        skill = db.session.get(Skill, skill_id) if skill_id else None
        if skill is None or status not in {"planned", "in_progress", "completed"}:
            abort(400)
        progress = LearningProgress.query.filter_by(user_id=current_user.id, skill_id=skill.id).first()
        if progress is None:
            progress = LearningProgress(user_id=current_user.id, skill_id=skill.id)
            db.session.add(progress)
        progress.status = status
        db.session.commit()
        flash("Learning progress updated.", "success")
        return redirect(url_for("main.roadmap"))

    required = set()
    if session.get("last_skill_gap"):
        required.update(session["last_skill_gap"].get("missing", []))
    recent_resume = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).first()
    resume_skills = set(recent_resume.analysis_json.get("skills", [])) if recent_resume else set()
    resume_skills.update(profile_skill_names(current_user))
    for job in Job.query.filter_by(active=True).all():
        required.update(skill.name for skill in job.skills if skill.name not in resume_skills)
    progress_by_name = {
        record.skill.name: record
        for record in LearningProgress.query.filter_by(user_id=current_user.id).all()
    }
    steps = []
    for name in sorted(required)[:12]:
        skill = Skill.query.filter_by(name=name).first()
        if skill is None:
            continue
        record = progress_by_name.get(name)
        steps.append({
            "skill": skill, "progress": record,
            "status": record.status if record else "planned",
            "link": LEARNING_LINKS.get(name, f"https://www.google.com/search?q=learn+{name.replace(' ', '+')}"),
        })
    return render_template("roadmap.html", steps=steps)


@main.route("/interview", methods=["GET", "POST"])
@login_required
def interview():
    if request.method == "POST":
        question_id = request.form.get("question_id", type=int)
        answer = clean_text(request.form.get("answer"), 8000)
        question = db.session.get(InterviewQuestion, question_id) if question_id else None
        if question is None or not answer:
            flash("Choose a question and write an answer before submitting.", "warning")
        else:
            db.session.add(InterviewAttempt(
                user_id=current_user.id, question_id=question.id, answer=answer,
                feedback=answer_feedback(answer),
            ))
            db.session.commit()
            flash("Practice answer saved with automated structure feedback.", "success")
            return redirect(url_for("main.interview"))
    category = request.args.get("category", "all")
    question_query = InterviewQuestion.query
    if category in {"technical", "hr"}:
        question_query = question_query.filter_by(category=category)
    questions = question_query.order_by(InterviewQuestion.category, InterviewQuestion.id).all()
    attempts = InterviewAttempt.query.filter_by(user_id=current_user.id).order_by(InterviewAttempt.created_at.desc()).limit(5).all()
    return render_template("interview.html", questions=questions, attempts=attempts, category=category)


@main.route("/applications", methods=["GET", "POST"])
@login_required
def applications():
    if request.method == "POST":
        app_id = request.form.get("application_id", type=int)
        status = request.form.get("status", "")
        application = db.session.get(Application, app_id) if app_id else None
        if application is None or application.user_id != current_user.id or status not in APPLICATION_STATUSES:
            abort(400)
        application.status = status
        application.notes = clean_text(request.form.get("notes"), 1000)
        db.session.commit()
        flash("Application tracking details updated.", "success")
        return redirect(url_for("main.applications"))
    items = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    saved = SavedOpportunity.query.filter_by(user_id=current_user.id).order_by(SavedOpportunity.saved_at.desc()).all()
    counts = Counter(item.status for item in items)
    return render_template("applications.html", applications=items, saved=saved, counts=counts, statuses=sorted(APPLICATION_STATUSES))


@main.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    if request.method == "POST":
        kind = request.form.get("kind")
        title = clean_text(request.form.get("title"), 180)
        company = clean_text(request.form.get("company"), 160)
        description = clean_text(request.form.get("description"), 4000)
        category = clean_text(request.form.get("category"), 100) or "Technology"
        location = clean_text(request.form.get("location"), 120) or "Remote"
        skill_names = [name.strip() for name in request.form.get("skills", "").split(",") if name.strip() in SKILL_CATALOG]
        if not title or not company or not description or kind not in {"job", "internship"}:
            flash("Title, company, description, and a valid opportunity type are required.", "danger")
        else:
            skills_for_item = Skill.query.filter(Skill.name.in_(skill_names)).all() if skill_names else []
            if kind == "job":
                item = Job(title=title, company=company, location=location, category=category, description=description)
            else:
                item = Internship(
                    title=title, company=company, location=location, category=category,
                    duration=clean_text(request.form.get("duration"), 80) or "12 weeks",
                    description=description,
                )
            item.skills = skills_for_item
            db.session.add(item)
            db.session.commit()
            flash(f"{kind.capitalize()} listing published.", "success")
            return redirect(url_for("main.admin"))
    return render_template(
        "admin.html", user_count=User.query.count(),
        job_count=Job.query.count(), internship_count=Internship.query.count(),
        application_count=Application.query.count(),
        users=User.query.order_by(User.created_at.desc()).limit(25).all(),
        jobs=Job.query.order_by(Job.created_at.desc()).limit(20).all(),
        internships=Internship.query.order_by(Internship.created_at.desc()).limit(20).all(),
    )


@main.route("/admin/user/<int:user_id>/role", methods=["POST"])
@login_required
def update_user_role(user_id):
    if not current_user.is_admin:
        abort(403)
    user = db.session.get(User, user_id)
    role = request.form.get("role", "")
    if user is None or role not in {"student", "admin"}:
        abort(400)
    if user.id == current_user.id and role != "admin":
        flash("You cannot remove your own administrator access.", "warning")
        return redirect(url_for("main.admin"))
    if user.is_admin and role == "student" and User.query.filter_by(role="admin").count() <= 1:
        flash("The last administrator cannot be demoted.", "warning")
        return redirect(url_for("main.admin"))
    user.role = role
    db.session.commit()
    flash(f"{user.full_name}'s role is now {role}.", "success")
    return redirect(url_for("main.admin"))


@main.route("/admin/opportunity/<kind>/<int:opportunity_id>/toggle", methods=["POST"])
@login_required
def toggle_opportunity(kind, opportunity_id):
    if not current_user.is_admin:
        abort(403)
    if kind not in {"job", "internship"}:
        abort(404)
    model = Job if kind == "job" else Internship
    item = db.session.get(model, opportunity_id)
    if item is None:
        abort(404)
    item.active = not item.active
    db.session.commit()
    flash("Listing visibility updated.", "success")
    return redirect(url_for("main.admin"))


@main.route("/api/csrf-token")
def csrf_api():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(csrf_token=session["_csrf_token"])


@main.route("/api/auth/register", methods=["POST"])
def api_register():
    payload = request_json_object()
    if payload is None:
        return jsonify(error="Expected a JSON object."), 400
    name = clean_text(payload.get("full_name"), 120)
    email = clean_text(payload.get("email"), 255).lower()
    password = payload.get("password", "")
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Provide a name and a valid email address."), 400
    if not isinstance(password, str) or not 10 <= len(password) <= 256:
        return jsonify(error="Password must contain 10 to 256 characters."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with that email already exists."), 409
    user = User(email=email, full_name=name, role="student", profile=StudentProfile())
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    rotate_csrf_token()
    return jsonify(id=user.id, email=user.email, full_name=user.full_name, role=user.role), 201


@main.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request_json_object()
    if payload is None:
        return jsonify(error="Expected a JSON object."), 400
    email = clean_text(payload.get("email"), 255).lower()
    password = payload.get("password", "")
    user = User.query.filter_by(email=email).first() if isinstance(password, str) and len(password) <= 256 else None
    if not user or not user.check_password(password):
        return jsonify(error="Email or password is incorrect."), 401
    login_user(user)
    rotate_csrf_token()
    return jsonify(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@main.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    rotate_csrf_token()
    return jsonify(status="signed_out")


@main.route("/api/auth/me")
@login_required
def api_current_user():
    return jsonify(id=current_user.id, email=current_user.email, full_name=current_user.full_name, role=current_user.role)


@main.route("/api/jobs")
def api_jobs():
    query = clean_text(request.args.get("q"), 120)
    listing = Job.query.filter_by(active=True)
    if query:
        term = f"%{query}%"
        listing = listing.filter(or_(Job.title.ilike(term), Job.company.ilike(term), Job.description.ilike(term)))
    return jsonify(items=[serialize_opportunity(item, "job", current_user if current_user.is_authenticated else None) for item in listing.order_by(Job.created_at.desc()).all()])


@main.route("/api/internships")
def api_internships():
    query = clean_text(request.args.get("q"), 120)
    listing = Internship.query.filter_by(active=True)
    if query:
        term = f"%{query}%"
        listing = listing.filter(or_(Internship.title.ilike(term), Internship.company.ilike(term), Internship.description.ilike(term)))
    return jsonify(items=[serialize_opportunity(item, "internship", current_user if current_user.is_authenticated else None) for item in listing.order_by(Internship.created_at.desc()).all()])


@main.route("/api/recommendations")
@login_required
def api_recommendations():
    results = []
    for kind, listing in (
        ("job", Job.query.filter_by(active=True).all()),
        ("internship", Internship.query.filter_by(active=True).all()),
    ):
        for item in listing:
            data = serialize_opportunity(item, kind, current_user)
            data["match"].update({"opportunity_type": kind})
            results.append(data)
    return jsonify(items=sorted(results, key=lambda item: item["match"]["match_percent"], reverse=True))


@main.route("/api/skill-gap", methods=["POST"])
@login_required
def api_skill_gap():
    payload = request_json_object()
    if payload is None:
        return jsonify(error="Expected a JSON object."), 400
    required = find_skills(clean_text(payload.get("required_skills"), 2000))
    owned = {name.casefold() for name in profile_skill_names(current_user)}
    matched = [name for name in required if name.casefold() in owned]
    missing = [name for name in required if name.casefold() not in owned]
    return jsonify(required=required, matched=matched, missing=missing)


@main.route("/api/applications", methods=["GET", "POST"])
@login_required
def api_applications():
    if request.method == "POST":
        payload = request_json_object()
        if payload is None:
            return jsonify(error="Expected a JSON object."), 400
        kind = payload.get("type")
        try:
            opportunity_id = int(payload.get("opportunity_id"))
        except (TypeError, ValueError):
            return jsonify(error="opportunity_id must be an integer."), 400
        if kind not in {"job", "internship"}:
            return jsonify(error="type must be job or internship."), 400
        item = resolve_opportunity(kind, opportunity_id)
        values = {"user_id": current_user.id, "job_id": item.id if kind == "job" else None, "internship_id": item.id if kind == "internship" else None}
        application = Application.query.filter_by(**values).first()
        if not application:
            application = Application(**values, status="applied")
            db.session.add(application)
            db.session.commit()
        return jsonify(id=application.id, status=application.status), 201
    entries = Application.query.filter_by(user_id=current_user.id).order_by(Application.applied_at.desc()).all()
    return jsonify(items=[{
        "id": entry.id, "status": entry.status, "applied_at": entry.applied_at.isoformat(),
        "type": "job" if entry.job else "internship",
        "opportunity": entry.job.title if entry.job else entry.internship.title,
    } for entry in entries])


@main.route("/api/resume-analysis", methods=["POST"])
@login_required
def api_resume_analysis():
    payload = request_json_object()
    if payload is None:
        return jsonify(error="Expected a JSON object."), 400
    text = clean_text(payload.get("text"), 50000)
    if len(text) < 20:
        return jsonify(error="Provide at least 20 characters of resume text."), 400
    return jsonify(analyze_resume(text))


@main.route("/api/admin/stats")
@login_required
def api_admin_stats():
    if not current_user.is_admin:
        abort(403)
    return jsonify(
        users=User.query.count(), jobs=Job.query.count(),
        internships=Internship.query.count(), applications=Application.query.count(),
    )


@main.route("/healthz")
def healthcheck():
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        current_app.logger.exception("Database health check failed")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok"), 200
