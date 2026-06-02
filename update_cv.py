"""
Run with: source venv/bin/activate && python manage.py shell < update_cv.py
"""
from resume.models import ProfessionalSummary, EmploymentHistory, Keyword, Resume

# ── Professional Summary ──────────────────────────────────────────────────────
ps = ProfessionalSummary.objects.get(pk=1134715505148723201)
ps.summary_html = (
    "I am a creative, self-starting technologist with a passion for problem-solving "
    "and building software that makes complex workflows simple. Proficient in full-stack "
    "development with a focus on server-side engineering using <strong>Django</strong>, "
    "<strong>FastAPI</strong>, and <strong>Flask</strong>.<br><br>"
    "I have built and deployed a range of production applications including "
    "<strong>Location Services</strong> apps (Google Maps/Places API integration), "
    "<strong>Financial</strong> apps (billing audits, commission tracking, cost-analysis "
    "pipelines), and <strong>Project Management</strong> tools (custom reporting dashboards, "
    "weighing systems, and operational recommendation engines).<br><br>"
    "On the cloud &amp; DevOps side I work regularly with <strong>Google Cloud Platform</strong> — "
    "Cloud Console, IAM, Service Accounts, API enablement, SSL/TLS certificates, and API "
    "keys — as well as <strong>AWS</strong>, Heroku, Postgres, and CockroachDB.<br><br>"
    "I also explore <strong>AI/ML</strong> in personal projects, including fine-tuning and "
    "deploying <strong>diffusion models</strong> (Stable Diffusion, ControlNet) and "
    "integrating <strong>LLMs</strong> (OpenAI, Anthropic Claude, open-source models) into "
    "application back-ends via prompt engineering and RAG pipelines."
)
ps.save()
print("✓ Professional Summary updated")

# ── Web Developer | Self ──────────────────────────────────────────────────────
wd = EmploymentHistory.objects.get(pk=1134715506739544065)
wd.description_html = (
    "<strong>Location Services Apps:</strong> Built Google Maps / Places API integrations "
    "for property-search and field-service routing tools, handling geocoding, distance-matrix "
    "calculations, and real-time map rendering.<br><br>"
    "<strong>Financial Apps:</strong> Developed billing-audit and commission-tracking systems "
    "that surface missed revenue; built cost-analysis pipelines processing data from "
    "OpenDataNYC API endpoints into clean, exportable reports.<br><br>"
    "<strong>Project Management Apps:</strong> Created custom project-weighing and priority "
    "scoring systems with role-based dashboards, delivering operational recommendations to "
    "executive stakeholders.<br><br>"
    "<strong>Web Frameworks:</strong> Delivered full-stack projects using <strong>Django</strong> "
    "(ORM, Celery, DRF), <strong>FastAPI</strong> (async REST APIs, Pydantic validation), and "
    "<strong>Flask</strong> (lightweight micro-services and internal tooling).<br><br>"
    "<strong>Google Cloud &amp; DevOps:</strong> Configured GCP projects via Cloud Console — "
    "IAM roles &amp; service accounts, API enablement, OAuth 2.0 credentials, SSL/TLS "
    "certificate management, and domain verification.<br><br>"
    "<strong>AI / ML:</strong> Experimented with and deployed diffusion models "
    "(Stable Diffusion, ControlNet pipelines) and integrated LLM APIs (OpenAI, Anthropic) "
    "into back-end workflows, including prompt engineering and basic RAG setups.<br><br>"
    "Also delivered a Django server for a 501(c) non-profit (122 East 83rd Street restoration), "
    "a Zillow-like real estate clone, and business sites for clients from barbershops to "
    "construction management firms."
)
wd.save()
print("✓ Web Developer (Self) updated")

# ── KM Associates ─────────────────────────────────────────────────────────────
km = EmploymentHistory.objects.get(pk=1134715506165907457)
km.description_html = (
    "Instrumental in building and maintaining custom Salesforce org, M365 Active Directory, "
    "and supporting technology infrastructure.<br><br>"
    "Developed custom Salesforce org from concept to launch — collaborating with stakeholders "
    "to leverage software systems that complement internal business processes.<br><br>"
    "Created <strong>audit software</strong> that has caught over <strong>$1M</strong> in "
    "potential missed billing to-date.<br><br>"
    "Designed a <strong>project-weighing system</strong> providing custom reports and "
    "operational recommendations to the Executive team.<br><br>"
    "Built Django / FastAPI projects to extract and transform data from multiple OpenDataNYC "
    "API endpoints into easily consumable interfaces.<br><br>"
    "<strong>Google Cloud Platform &amp; DevOps:</strong> Managed GCP projects via Cloud "
    "Console; configured IAM roles, service accounts, and scoped API keys; provisioned "
    "SSL/TLS certificates and handled domain &amp; DNS configuration; integrated GCP APIs "
    "(Maps, Places, Geocoding) into production workflows.<br><br>"
    "Developed scripts supporting business processes including data migration from legacy "
    "systems and statistical analysis for marketing and advertising.<br><br>"
    "Participated in daily stand-ups, sprint and release planning, retrospectives, and "
    "Agile ceremonies. Owned bug-fix solutions through delivery. Supported external "
    "Salesforce developers on day-to-day development, configuration, and infrastructure."
)
km.save()
print("✓ KM Associates updated")

# ── New Keywords ──────────────────────────────────────────────────────────────
resume = Resume.objects.get(pk=1134715505546166273)

new_keywords = [
    # Web frameworks
    ("FastAPI", "web"),
    ("Flask", "web"),
    ("Celery", "web"),
    ("REST APIs", "web"),
    # Languages / tech
    ("TypeScript", "language"),
    # Cloud / DevOps
    ("Google Cloud Platform", "other"),
    ("GCP IAM", "other"),
    ("API Keys & Certs", "other"),
    ("DevOps", "other"),
    ("CI/CD", "other"),
    ("Docker", "other"),
    # AI / ML
    ("LLMs", "other"),
    ("Diffusion Models", "other"),
    ("Generative AI", "other"),
    ("Prompt Engineering", "other"),
    ("RAG Pipelines", "other"),
]

for name, category in new_keywords:
    kw, created = Keyword.objects.get_or_create(name=name, defaults={"category": category})
    resume.keywords.add(kw)
    status = "created" if created else "exists"
    print(f"  keyword '{name}' ({status})")

print("✓ Keywords updated")
print("\nAll done!")
