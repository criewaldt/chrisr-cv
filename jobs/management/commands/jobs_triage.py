"""Score pending postings with the cheap tier-1 model."""
import asyncio

from django.core.management.base import BaseCommand

from jobs.ai.client import AccountError, MissingAPIKey
from jobs.models import JobPosting, SearchProfile
from jobs.triage_runner import select_for_triage, triage


class Command(BaseCommand):
    help = 'Score pre-filter survivors against the search profile (tier 1, cheap).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Max postings to score this run')
        parser.add_argument('--days', type=int, help='Only postings posted within N days')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be scored and the estimated cost')

    def handle(self, *args, **opts):
        profile = SearchProfile.active()
        if profile is None:
            self.stderr.write(self.style.ERROR('No active SearchProfile.'))
            return

        postings, capped = select_for_triage(profile, limit=opts['limit'],
                                             max_age_days=opts['days'])
        if not postings:
            self.stdout.write('Nothing pending triage.')
            return

        if capped:
            self.stdout.write(self.style.WARNING(
                f'More survivors than the {opts["limit"] or profile.max_triage_per_run} cap; '
                'free keyword ranking chose this run\'s batch. The rest stay queued.'))

        if opts['dry_run']:
            self.stdout.write(f'\nWould score {len(postings)} postings '
                              f'(~${0.0027 * len(postings):.2f} at Haiku rates):')
            for p in postings[:20]:
                self.stdout.write(f'  {p.title[:56]:56s} @ {p.company[:20]}')
            if len(postings) > 20:
                self.stdout.write(f'  ... and {len(postings) - 20} more')
            return

        self.stdout.write(f'Scoring {len(postings)} postings...')
        try:
            scored, errors, stats = asyncio.run(triage(postings, profile))
        except (AccountError, MissingAPIKey) as exc:
            self.stderr.write(self.style.ERROR(f'\n{exc}'))
            self.stderr.write('No postings were scored and nothing was charged. '
                              'They stay queued for the next run.')
            return

        self.stdout.write(self.style.SUCCESS(
            f'\nscored {scored} | failed {len(errors)} | cost ${stats["cost"]:.4f} | '
            f'cached input tokens {stats["cached"]:,}'))
        if stats['cached'] == 0 and scored > 1:
            from jobs.ai.client import TRIAGE_MODEL, cache_minimum
            self.stdout.write(self.style.NOTICE(
                f'  No prompt cache: the stable prefix is under {TRIAGE_MODEL}\'s '
                f'{cache_minimum(TRIAGE_MODEL):,}-token minimum. Expected, not a fault.'))
        for posting, err in errors[:5]:
            self.stdout.write(self.style.ERROR(f'  ! {posting.title[:40]}: {str(err)[:100]}'))

        top = (JobPosting.objects.filter(status=JobPosting.STATUS_SCORED)
               .select_related('score').order_by('-score__fit_score')[:15])
        self.stdout.write('\nTop scored:')
        for p in top:
            self.stdout.write(f'  {p.score.fit_score:3d} {p.score.verdict:9s} '
                              f'{p.title[:44]:44s} @ {p.company[:18]:18s}')
            self.stdout.write(f'      {p.score.reasoning[:110]}')
