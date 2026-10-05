import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from students.models import Student

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png")


class Command(BaseCommand):
    help = (
        "Bulk-assign student photos from a folder. Each image file must be named "
        "after the student's student_id, e.g. STU001.jpg for the student with "
        "student_id=STU001."
    )

    def add_arguments(self, parser):
        parser.add_argument("folder", type=str, help="Path to the folder of photos")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace a photo even if the student already has one",
        )

    def handle(self, *args, **options):
        folder = options["folder"]
        overwrite = options["overwrite"]

        if not os.path.isdir(folder):
            raise CommandError(f"Folder not found: {folder}")

        assigned, skipped, unmatched = [], [], []

        for filename in sorted(os.listdir(folder)):
            name, ext = os.path.splitext(filename)
            if ext.lower() not in VALID_EXTENSIONS:
                continue

            student = Student.objects.filter(student_id=name).first()
            if not student:
                unmatched.append(filename)
                continue

            if student.photo and not overwrite:
                skipped.append(filename)
                continue

            filepath = os.path.join(folder, filename)
            with open(filepath, "rb") as f:
                student.photo.save(filename, File(f), save=True)
            assigned.append(filename)

        self.stdout.write(self.style.SUCCESS(f"Assigned: {len(assigned)}"))
        for filename in assigned:
            self.stdout.write(f"  ✓ {filename}")

        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped (already has a photo): {len(skipped)}"))
            for filename in skipped:
                self.stdout.write(f"  - {filename}")

        if unmatched:
            self.stdout.write(self.style.ERROR(f"Unmatched (no student with that student_id): {len(unmatched)}"))
            for filename in unmatched:
                self.stdout.write(f"  ? {filename}")
