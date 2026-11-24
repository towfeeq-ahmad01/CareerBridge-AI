import io
import tempfile
import unittest

from backend import create_app, db
from backend.models import Application, InterviewQuestion, Internship, Job, LearningProgress, Skill, User
from backend.seed import seed_catalog


def text_pdf():
    content = b"BT /F1 12 Tf 72 720 Td (Education BCA University Projects Python Flask SQL and experience student@example.com) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


class CareerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "UPLOAD_FOLDER": self.upload_dir.name,
            "WTF_CSRF_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        seed_catalog()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.upload_dir.cleanup()

    def csrf(self):
        response = self.client.get("/api/csrf-token")
        return response.get_json()["csrf_token"]

    def register(self, email="student@example.com"):
        token = self.csrf()
        return self.client.post("/register", data={
            "_csrf_token": token,
            "full_name": "Test Student",
            "email": email,
            "password": "secure-test-password",
        }, follow_redirects=True)

    def test_registration_password_hash_and_authenticated_dashboard(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(email="student@example.com").one()
        self.assertNotEqual(user.password_hash, "secure-test-password")
        self.assertTrue(user.check_password("secure-test-password"))
        self.assertIsNotNone(user.profile)
        self.assertIn(b"Good to see you", response.data)

    def test_job_search_skill_matching_and_application_tracking(self):
        self.register()
        profile = User.query.filter_by(email="student@example.com").one().profile
        profile.skills = [Skill.query.filter_by(name=name).one() for name in ("Python", "SQL")]
        db.session.commit()
        response = self.client.get("/api/recommendations")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        python_role = next(item for item in items if item["title"] == "Junior Python Developer")
        self.assertGreater(python_role["match"]["match_percent"], 0)
        self.assertIn("Python", python_role["match"]["matched_skills"])
        self.assertEqual(self.client.get("/jobs?q=Python").status_code, 200)
        token = self.csrf()
        created = self.client.post("/api/applications", json={
            "type": "job", "opportunity_id": python_role["id"],
        }, headers={"X-CSRFToken": token})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Application.query.count(), 1)
        self.assertEqual(self.client.get("/api/applications").get_json()["items"][0]["status"], "applied")

    def test_resume_analysis_endpoint_and_invalid_input(self):
        self.register()
        token = self.csrf()
        result = self.client.post("/api/resume-analysis", json={
            "text": "Education BCA University. Projects in Python and Flask. Email: student@example.com. Experience building SQL applications."
        }, headers={"X-CSRFToken": token})
        self.assertEqual(result.status_code, 200)
        self.assertIn("Python", result.get_json()["skills"])
        self.assertGreaterEqual(result.get_json()["score"], 40)
        invalid = self.client.post("/api/resume-analysis", json={"text": "short"}, headers={"X-CSRFToken": token})
        self.assertEqual(invalid.status_code, 400)

    def test_admin_authorization_and_admin_stats(self):
        self.register()
        self.assertEqual(self.client.get("/api/admin/stats").status_code, 403)
        user = User.query.filter_by(email="student@example.com").one()
        user.role = "admin"
        db.session.commit()
        stats = self.client.get("/api/admin/stats")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["jobs"], Job.query.count())
        self.assertGreater(Internship.query.count(), 0)
        self.assertGreater(InterviewQuestion.query.count(), 0)

    def test_csrf_required_for_state_changes(self):
        response = self.client.post("/register", data={
            "full_name": "No Token", "email": "no-token@example.com", "password": "secure-test-password",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.query.count(), 0)

    def test_json_authentication_lifecycle(self):
        token = self.csrf()
        malformed = self.client.post(
            "/api/auth/register", json=[], headers={"X-CSRFToken": token},
        )
        self.assertEqual(malformed.status_code, 400)
        registered = self.client.post("/api/auth/register", json={
            "full_name": "API Student",
            "email": "api-student@example.com",
            "password": "secure-api-password",
        }, headers={"X-CSRFToken": token})
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["role"], "student")
        token = self.csrf()
        self.assertEqual(self.client.post(
            "/api/auth/logout", headers={"X-CSRFToken": token},
        ).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        token = self.csrf()
        login = self.client.post("/api/auth/login", json={
            "email": "api-student@example.com", "password": "secure-api-password",
        }, headers={"X-CSRFToken": token})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_resume_upload_rejects_non_pdf(self):
        self.register()
        token = self.csrf()
        response = self.client.post("/resume", data={
            "_csrf_token": token,
            "resume": (io.BytesIO(b"plain text"), "resume.txt"),
        }, content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"Only PDF resumes are supported", response.data)

    def test_resume_upload_extracts_text_and_saves_analysis(self):
        self.register()
        token = self.csrf()
        response = self.client.post("/resume", data={
            "_csrf_token": token,
            "resume": (io.BytesIO(text_pdf()), "student-resume.pdf"),
        }, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Resume analyzed", response.data)
        from backend.models import Resume
        resume = Resume.query.one()
        self.assertIn("Python", resume.analysis_json["skills"])
        import os
        self.assertTrue(os.path.isfile(os.path.join(self.upload_dir.name, resume.storage_key)))

    def test_roadmap_progress_creates_record_for_current_user(self):
        self.register()
        skill = Skill.query.filter_by(name="Python").one()
        response = self.client.post("/roadmap", data={
            "_csrf_token": self.csrf(),
            "skill_id": skill.id,
            "status": "in_progress",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LearningProgress.query.one().status, "in_progress")

    def test_public_and_student_pages_render(self):
        for path in ("/", "/about", "/jobs", "/internships"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.register()
        for path in (
            "/dashboard", "/resume", "/skills", "/roadmap", "/interview",
            "/applications", "/opportunity/job/1", "/opportunity/internship/1",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        user = User.query.filter_by(email="student@example.com").one()
        user.role = "admin"
        db.session.commit()
        self.assertEqual(self.client.get("/admin").status_code, 200)


if __name__ == "__main__":
    unittest.main()
