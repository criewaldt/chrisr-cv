"""Run a discovery pass. Free -- no LLM calls anywhere in this command."""
import asyncio
import json

from django.core.management.base import BaseCommand

from jobs.discovery import discover
from jobs.models import JobPosting, JobSource, SearchProfile


class Command(BaseCommand):
    help = 'Fetch postings from enabled sources, dedupe, and pre-filter them.'

    def add_arguments(self, parser):
        parser.add_argument('--source', help='Limit to one adapter kind (e.g. greenhouse)')
        parser.add_argument('--config', help='Ad-hoc JSON config; runs without saving a JobSource')
        parser.add_argument('--dry-run', action='store_true', help='Fetch and filter, write nothing')
        parser.add_argument('--show', type=int, default=15, help='How many survivors to print')

    def handle(self, *args, **opts):
        profile = SearchProfile.active()
        if profile is None:
            self.stderr.write(self.style.ERROR('No active SearchProfile. Create one first.'))
            return

        sources = None
        if opts['config']:
            if not opts['source']:
                self.stderr.write(self.style.ERROR('--config requires --source'))
                return
            sources = [JobSource(kind=opts['source'], config=json.loads(opts['config']),
                                 label=f'ad-hoc {opts["source"]}')]
        elif opts['source']:
            sources = list(JobSource.objects.filter(enabled=True, kind=opts['source']))
            if not sources:
                self.stderr.write(self.style.WARNING(f'No enabled sources of kind {opts["source"]!r}'))
                return

        run = asyncio.run(discover(slot='manual', sources=sources, profile=profile,
                                   dry_run=opts['dry_run']))

        mode = 'DRY RUN' if opts['dry_run'] else 'saved'
        self.stdout.write(self.style.SUCCESS(
            f'\n{run.sources_run} sources | {run.found} fetched | '
            f'{run.new} passed | {run.filtered} filtered | {mode}'))

        for err in run.errors:
            self.stdout.write(self.style.ERROR(f"  ! {err['source']}: {err['error'][:120]}"))

        rows = (getattr(run, '_preview', None)
                if opts['dry_run'] else
                list(JobPosting.objects.filter(status=JobPosting.STATUS_NEW)
                     .order_by('-discovered_at')[:opts['show']]))
        survivors = [r for r in (rows or []) if r.status == JobPosting.STATUS_NEW]

        if survivors:
            self.stdout.write('\nPassed the pre-filter (these are what triage would cost money on):')
            for p in survivors[:opts['show']]:
                salary = f'  {p.salary_display}' if p.salary_display else ''
                self.stdout.write(f'  {p.title[:56]:56s} @ {p.company[:18]:18s} '
                                  f'{p.location[:24]:24s}{salary}')

        if opts['dry_run'] and rows:
            filtered = [r for r in rows if r.status == JobPosting.STATUS_FILTERED]
            if filtered:
                self.stdout.write(f'\nRejected for free ({len(filtered)}) — sample:')
                for p in filtered[:8]:
                    self.stdout.write(f'  {p.title[:52]:52s} -> {p.filter_reason}')
