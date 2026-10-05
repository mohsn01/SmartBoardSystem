from django.db import models
from students.models import Student
from subjects.models import Subject


class Mark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    exam_mark = models.FloatField()
    homework_mark = models.FloatField()

    average = models.FloatField(blank=True, null=True)

    class Meta:
        unique_together = ("student", "subject")

    def save(self, *args, source="manual", **kwargs):
        is_new = self.pk is None
        changed = is_new
        if not is_new:
            previous = Mark.objects.filter(pk=self.pk).values("exam_mark", "homework_mark").first()
            changed = previous is not None and (
                previous["exam_mark"] != self.exam_mark or previous["homework_mark"] != self.homework_mark
            )

        self.average = (self.exam_mark + self.homework_mark) / 2
        super().save(*args, **kwargs)

        if changed:
            MarkHistory.objects.create(
                student=self.student,
                subject=self.subject,
                exam_mark=self.exam_mark,
                homework_mark=self.homework_mark,
                average=self.average,
                source=source,
            )

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name}"


class MarkHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_mark = models.FloatField()
    homework_mark = models.FloatField()
    average = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=20, default="manual")

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} @ {self.recorded_at:%Y-%m-%d}"