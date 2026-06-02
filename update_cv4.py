"""
Run with: source venv/bin/activate && python manage.py shell < update_cv4.py
"""
from resume.models import EmploymentHistory

km = EmploymentHistory.objects.get(pk=1134715506165907457)
km.description_html = km.description_html.replace(
    "<strong>Google Cloud Platform &amp; DevOps:</strong> Managed GCP projects via Cloud "
    "Console; configured IAM roles, service accounts, and scoped API keys; provisioned "
    "SSL/TLS certificates and handled domain &amp; DNS configuration; integrated GCP APIs "
    "(Maps, Places, Geocoding) into production workflows.",
    "<strong>Cloud &amp; DevOps (GCP + AWS):</strong> Own all DevOps responsibilities across "
    "both platforms. On <strong>GCP</strong>: managed Cloud Console, IAM roles, service "
    "accounts, scoped API keys, SSL/TLS certificates, domain &amp; DNS configuration, and "
    "GCP API integrations (Maps, Places, Geocoding). On <strong>AWS</strong>: provisioned and "
    "maintain <strong>S3</strong> buckets for file storage, managing bucket policies, access "
    "controls, and lifecycle rules."
)
km.save()
print("✓ KM Associates AWS/DevOps updated")
