"""
Run with: source venv/bin/activate && python manage.py shell < update_cv3.py
"""
from resume.models import EmploymentHistory, ProfessionalSummary

ps = ProfessionalSummary.objects.get(pk=1134715505148723201)
ps.summary_html = (
    "I am a creative, self-starting technologist with a passion for problem-solving "
    "and building software that makes complex workflows simple. I specialize in "
    "<strong>optimizing and innovating financial and project management processes</strong> — "
    "turning manual, error-prone operations into automated, data-driven systems.<br><br>"
    "Proficient in full-stack development with a focus on server-side engineering using "
    "<strong>Django</strong>, <strong>FastAPI</strong>, and <strong>Flask</strong>.<br><br>"
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

from resume.models import EmploymentHistory

km = EmploymentHistory.objects.get(pk=1134715506165907457)
km.description_html = (
    "Instrumental in building and maintaining custom Salesforce org, M365 Active Directory, "
    "and supporting technology infrastructure.<br><br>"
    "Developed and launched a custom Salesforce org serving <strong>60 users</strong> — "
    "collaborating with stakeholders to leverage software systems that complement internal "
    "business processes. Maintains <strong>100% uptime since January 2024</strong>.<br><br>"
    "Designed, built, and maintain <strong>purchase order and retainer workflows</strong> that "
    "automate and simplify end-to-end procurement and billing processes.<br><br>"
    "Created <strong>audit software</strong> that recovered over <strong>$1M in missed "
    "billings</strong> and saved hundreds of man-hours of manual reconciliation work.<br><br>"
    "Designed a <strong>project-weighing system</strong> that scores and prioritizes over "
    "<strong>2,500 projects per year</strong> — each comprising 20–50 individual services — "
    "delivering custom reports and operational recommendations to the Executive team.<br><br>"
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
print("✓ KM Associates updated with all metrics")
