# resume/management/commands/import_resume_json.py
"""
Usage:
  1) Put your JSON into a file, e.g. data/resume.json
  2) Run:
     python manage.py import_resume_json data/resume.json

Notes:
- Idempotent-ish: it clears/rewires M2M links for the Resume it imports.
- It will create related records if they don't exist.
- It will update the Resume basic fields.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from resume.models import (
    Resume,
    ProfessionalSummary,
    EmploymentHistory,
    Award,
    Education,
    Keyword,
)


def _req(fields: dict, key: str) -> Any:
    if key not in fields:
        raise CommandError(f"Missing required key: fields['{key}']")
    return fields[key]


def _parse_date_or_none(value):
    if value in (None, "", "null"):
        return None
    d = parse_date(value)
    if not d:
        raise CommandError(f"Invalid date format: {value!r} (expected YYYY-MM-DD)")
    return d


class Command(BaseCommand):
    help = "Import Resume JSON (custom structure) into Resume + related models."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to JSON file containing the resume payload (list of objects).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        json_path = Path(options["json_path"])
        if not json_path.exists():
            raise CommandError(f"File not found: {json_path}")

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        if not isinstance(payload, list) or not payload:
            raise CommandError("Expected a non-empty JSON list at the top level.")

        # Your sample data has one item
        item = payload[0]
        if not isinstance(item, dict) or "fields" not in item:
            raise CommandError("Expected objects with a 'fields' key.")

        fields = item["fields"]

        name = _req(fields, "name")
        email = _req(fields, "email")
        phone = _req(fields, "phone")
        desired_title = fields.get("desired_title")
        current_title = fields.get("current_title")

        # ---- Professional Summary (FK) ----
        ps_data = _req(fields, "professional_summary")
        if not isinstance(ps_data, dict):
            raise CommandError("fields['professional_summary'] must be an object.")

        # Your model stores HTML, JSON has plain text; we'll store as-is.
        # If you later want to wrap in <p>...</p>, do it here.
        ps_summary_html = ps_data.get("summary", "") or ""
        ps_highlights = ps_data.get("highlights", "") or ""

        professional_summary, _ = ProfessionalSummary.objects.get_or_create(
            summary_html=ps_summary_html,
            highlights=ps_highlights,
        )

        # ---- Resume (main record) ----
        # Use email as a stable natural key; adjust if you want by name instead.
        resume, created = Resume.objects.update_or_create(
            email=email,
            defaults={
                "name": name,
                "phone": phone,
                "desired_title": desired_title,
                "current_title": current_title,
                "professional_summary": professional_summary,
            },
        )

        # ---- Employment History (M2M) ----
        resume.employment_history.clear()

        eh_list = fields.get("employment_history", []) or []
        if not isinstance(eh_list, list):
            raise CommandError("fields['employment_history'] must be a list.")

        for eh in eh_list:
            if not isinstance(eh, dict):
                raise CommandError("Each employment_history item must be an object.")

            job_title = _req(eh, "job_title")
            company_name = _req(eh, "company_name")
            location = _req(eh, "location")
            start_date = _parse_date_or_none(_req(eh, "start_date"))
            end_date = _parse_date_or_none(eh.get("end_date"))
            description_html = eh.get("description", "") or ""
            is_current = bool(eh.get("is_current", False))
            sort_order = int(eh.get("sort_order", 0))

            # A reasonable natural key for dedupe:
            # company + title + start_date + sort_order
            employment_obj, _ = EmploymentHistory.objects.update_or_create(
                company_name=company_name,
                job_title=job_title,
                start_date=start_date,
                defaults={
                    "location": location,
                    "end_date": end_date,
                    "description_html": description_html,
                    "is_current": is_current,
                    "sort_order": sort_order,
                },
            )

            resume.employment_history.add(employment_obj)

        # ---- Awards (M2M) ----
        resume.awards.clear()
        awards_list = fields.get("awards", []) or []
        if not isinstance(awards_list, list):
            raise CommandError("fields['awards'] must be a list.")

        for a in awards_list:
            if not isinstance(a, dict):
                raise CommandError("Each awards item must be an object.")
            award, _ = Award.objects.update_or_create(
                name=_req(a, "name"),
                defaults={"description": a.get("description", "") or ""},
            )
            resume.awards.add(award)

        # ---- Education (M2M) ----
        resume.education.clear()
        edu_list = fields.get("education", []) or []
        if not isinstance(edu_list, list):
            raise CommandError("fields['education'] must be a list.")

        for e in edu_list:
            if not isinstance(e, dict):
                raise CommandError("Each education item must be an object.")
            degree = _req(e, "degree")
            school = _req(e, "school")
            time = _req(e, "time")

            edu_obj, _ = Education.objects.update_or_create(
                degree=degree,
                school=school,
                defaults={"time": time},
            )
            resume.education.add(edu_obj)

        # ---- Keywords (M2M) ----
        resume.keywords.clear()
        kw_list = fields.get("keywords", []) or []
        if not isinstance(kw_list, list):
            raise CommandError("fields['keywords'] must be a list.")

        for k in kw_list:
            if not isinstance(k, dict):
                raise CommandError("Each keywords item must be an object.")
            name = _req(k, "name")
            category = k.get("category", "") or ""
            kw_obj, _ = Keyword.objects.update_or_create(
                name=name,
                category=category,
            )
            resume.keywords.add(kw_obj)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported Resume (id={resume.id}, created={created}) with "
                f"{resume.employment_history.count()} jobs, "
                f"{resume.awards.count()} awards, "
                f"{resume.education.count()} education items, "
                f"{resume.keywords.count()} keywords."
            )
        )
