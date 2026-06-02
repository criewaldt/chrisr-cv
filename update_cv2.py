"""
Run with: source venv/bin/activate && python manage.py shell < update_cv2.py
"""
from resume.models import EmploymentHistory, Keyword

# ── Audit software bullet ─────────────────────────────────────────────────────
km = EmploymentHistory.objects.get(pk=1134715506165907457)
km.description_html = km.description_html.replace(
    "Developed custom Salesforce org from concept to launch — collaborating with stakeholders "
    "to leverage software systems that complement internal business processes.",
    "Developed and launched a custom Salesforce org serving <strong>60 users</strong> — "
    "collaborating with stakeholders to leverage software systems that complement internal "
    "business processes."
).replace(
    "Created <strong>audit software</strong> that has caught over <strong>$1M</strong> in "
    "potential missed billing to-date.",
    "Created <strong>audit software</strong> that recovered over <strong>$1M in missed "
    "billings</strong> and saved hundreds of man-hours of manual reconciliation work."
)
km.save()
print("✓ Audit bullet updated")

# ── Keyword category splits ───────────────────────────────────────────────────
cloud_keywords = [
    "Heroku", "AWS", "Google Cloud Platform", "GCP IAM",
    "API Keys & Certs", "DevOps", "CI/CD", "Docker",
]
ai_keywords = [
    "LLMs", "Diffusion Models", "Generative AI",
    "Prompt Engineering", "RAG Pipelines",
]
methodology_keywords = [
    "GitHub", "Data Migration", "Code Review", "Agile",
    "Automated Testing", "Unit Testing", "Scrum", "SDLC",
]

for name in cloud_keywords:
    updated = Keyword.objects.filter(name=name).update(category="cloud")
    print(f"  cloud: '{name}' ({'ok' if updated else 'not found'})")

for name in ai_keywords:
    updated = Keyword.objects.filter(name=name).update(category="ai")
    print(f"  ai: '{name}' ({'ok' if updated else 'not found'})")

for name in methodology_keywords:
    updated = Keyword.objects.filter(name=name).update(category="methodology")
    print(f"  methodology: '{name}' ({'ok' if updated else 'not found'})")

print("✓ Keyword categories updated")
print("\nAll done!")
