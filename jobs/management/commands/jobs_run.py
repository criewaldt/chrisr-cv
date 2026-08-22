"""One scheduled cycle: discover, pre-filter, triage, email.

Heroku Scheduler is free but UTC-only, so 8:30am ET would silently drift to 9:30am
for half the year. The workaround is two Scheduler entries per slot -- one for EDT,
one for EST -- with this command guarding so exactly one of the pair does the work:

  slot     EDT entry (UTC)   EST entry (UTC)
  morning     12:30             13:30
  midday      16:00             17:00
  evening     21:00             22:00

Both guards are needed. The clock guard alone lets the EST twin fire an hour early
in summer; the idempotency guard alone lets whichever twin runs first win, at the
wrong time. Together, one run happens, on time, year-round. The off-season twin
exits in about three seconds.
"""
import asyncio

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.discovery import discover
from jobs.emails import send_digest
from jobs.models import DigestSend, SearchProfile
from jobs.triage_runner import select_for_triage, triage

# Wall-clock targets in the project timezone (America/New_York).
SLOT_TIMES = {'morning': (8, 30), 'midday': (12, 0), 'evening': (17, 0)}
TOLERANCE_MINUTES = 45


class Command(BaseCommand):
    help = 'Run one scheduled cycle for a slot: discover, triage, then email.'

    def add_arguments(self, parser):
        parser.add_argument('slot', choices=sorted(SLOT_TIMES))
        parser.add_argument('--force', action='store_true',
                            help='Bypass both the clock and idempotency guards')
        parser.add_argument('--skip-email', action='store_true')
        parser.add_argument('--limit', type=int, help='Cap postings triaged this run')

    def handle(self, *args, **opts):
        slot = opts['slot']
        if not opts['force']:
            blocked = self._guard(slot)
            if blocked:
                self.stdout.write(f'skipped: {blocked}')
                return

        profile = SearchProfile.active()
        if profile is None:
            self.stderr.write(self.style.ERROR('No active SearchProfile.'))
            return

        run = asyncio.run(discover(slot=slot, profile=profile))
        self.stdout.write(f'discovered: {run.found} fetched, {run.new} passed, '
                          f'{run.filtered} filtered, {len(run.errors)} source errors')

        postings, capped = select_for_triage(profile, limit=opts['limit'])
        scored = 0
        if postings:
            try:
                scored, errors, stats = asyncio.run(triage(postings, profile))
                run.scored = scored
                run.cost_usd = stats['cost']
                run.save(update_fields=['scored', 'cost_usd'])
                self.stdout.write(f'triaged: {scored} scored, {len(errors)} failed, '
                                  f'${stats["cost"]:.4f}'
                                  + (' (capped; rest stay queued)' if capped else ''))
            except Exception as exc:
                # A triage failure must not cost the digest -- discovery already
                # succeeded and there may be plenty worth emailing about.
                self.stderr.write(self.style.ERROR(f'triage failed: {exc}'))

        if opts['skip_email']:
            self.stdout.write('email skipped')
            return

        record, _body = send_digest(slot)
        if record.skipped:
            self.stdout.write(f'digest skipped: {record.skip_reason}')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'digest sent: {record.new_job_count} new, {record.applied_count} applied'))

    def _guard(self, slot, now=None):
        """Return a reason to skip, or None to proceed."""
        now = now or timezone.localtime()
        hour, minute = SLOT_TIMES[slot]
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        drift = abs((now - target).total_seconds()) / 60
        if drift > TOLERANCE_MINUTES:
            return (f'local time {now:%H:%M %Z} is {drift:.0f} min from the '
                    f'{hour:02d}:{minute:02d} {slot} target (DST twin)')

        already = DigestSend.objects.filter(
            slot=slot, sent_at__date=now.date()).exists()
        if already:
            return f'{slot} digest already ran today'
        return None
