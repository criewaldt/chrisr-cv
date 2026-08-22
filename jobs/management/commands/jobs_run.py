"""Run a full cycle from the CLI: discover, triage, and optionally email.

The dashboard's "Fetch new jobs" button is the normal path -- there are no
scheduled tasks. This exists for running a sweep from a terminal, and for sending
yourself a digest of what turned up, which the button does not do (you are already
looking at the inbox when you press it).
"""
import asyncio

from django.core.management.base import BaseCommand

from jobs.discovery import discover
from jobs.emails import send_digest
from jobs.models import SearchProfile
from jobs.triage_runner import select_for_triage, triage


class Command(BaseCommand):
    help = 'Discover, triage, and optionally email a digest.'

    def add_arguments(self, parser):
        parser.add_argument('--email', action='store_true',
                            help='Send a digest of what turned up (off by default)')
        parser.add_argument('--limit', type=int, help='Cap postings triaged this run')
        parser.add_argument('--no-triage', action='store_true',
                            help='Discover and pre-filter only; spend nothing')

    def handle(self, *args, **opts):
        profile = SearchProfile.active()
        if profile is None:
            self.stderr.write(self.style.ERROR('No active SearchProfile.'))
            return

        run = asyncio.run(discover(slot='cli', profile=profile))
        self.stdout.write(f'discovered: {run.found:,} fetched, {run.new} new, '
                          f'{run.filtered} filtered free, {len(run.errors)} source errors')
        for err in run.errors[:5]:
            self.stdout.write(self.style.ERROR(f"  ! {err['source']}: {err['error'][:100]}"))

        if opts['no_triage']:
            self.stdout.write('triage skipped')
        else:
            postings, capped = select_for_triage(profile, limit=opts['limit'])
            if postings:
                try:
                    scored, errors, stats = asyncio.run(triage(postings, profile))
                    run.scored = scored
                    run.cost_usd = stats['cost']
                    run.save(update_fields=['scored', 'cost_usd'])
                    self.stdout.write(
                        f'triaged: {scored} scored, {len(errors)} failed, ${stats["cost"]:.4f}'
                        + (' (capped; rest stay queued)' if capped else ''))
                except Exception as exc:
                    # Discovery already succeeded and saved; a triage failure must
                    # not discard that work.
                    self.stderr.write(self.style.ERROR(f'triage failed: {exc}'))
            else:
                self.stdout.write('nothing pending triage')

        if not opts['email']:
            return
        record, _body = send_digest('cli')
        if record.skipped:
            self.stdout.write(f'digest skipped: {record.skip_reason}')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'digest sent: {record.new_job_count} new, {record.applied_count} applied'))
