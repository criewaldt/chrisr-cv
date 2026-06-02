from resume.models import Education, Resume

edu, created = Education.objects.get_or_create(
    degree="Full-Stack Web Development",
    school="Dev Bootcamp",
    defaults={"time": "2016"}
)

resume = Resume.objects.get(pk=1134715505546166273)
resume.education.add(edu)

print(f"✓ Education '{'created' if created else 'exists'}': {edu.degree} — {edu.school} ({edu.time})")
