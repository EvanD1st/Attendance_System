from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from attendance_app.services import finalize_attendance


class Command(BaseCommand):
    help = "Idempotently finalize completed shifts as absent or missing clock-out."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="work_date",
            help="Work date in YYYY-MM-DD format; defaults to yesterday.",
        )

    def handle(self, *args, **options):
        if options["work_date"]:
            try:
                work_date = date.fromisoformat(options["work_date"])
            except ValueError as exc:
                raise CommandError("--date must use YYYY-MM-DD format.") from exc
        else:
            work_date = timezone.localdate() - timedelta(days=1)
        counts = finalize_attendance(work_date)
        self.stdout.write(self.style.SUCCESS(f"Finalized {work_date}: {counts}"))
