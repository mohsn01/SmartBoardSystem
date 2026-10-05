from django.db import models
from students.models import Student
from subjects.models import Question, Subject, Topic


class ClassSession(models.Model):
    STATE_ATTENDANCE, STATE_IDLE, STATE_PENDING, STATE_CONFIRMED = "attendance", "idle", "pending", "confirmed"
    STATE_CHOICES = [
        (STATE_ATTENDANCE, "Taking attendance"),
        (STATE_IDLE, "Idle"),
        (STATE_PENDING, "Pending"),
        (STATE_CONFIRMED, "Confirmed"),
    ]

    classroom = models.CharField(max_length=50)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_IDLE)
    current_student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    current_average = models.FloatField(null=True, blank=True)
    current_priority = models.CharField(max_length=20, blank=True)
    current_status = models.CharField(max_length=30, blank=True)
    candidate_names = models.JSONField(default=list, blank=True)
    skipped_ids = models.JSONField(default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.classroom} - {self.subject.name} ({self.state})"


class Attendance(models.Model):
    STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE = "present", "absent", "late"
    STATUS_CHOICES = [
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
    ]

    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("class_session", "student")

    def __str__(self):
        return f"{self.student.full_name} - {self.class_session} ({self.status})"


class BoardSelection(models.Model):
    OUTCOME_CHOICES = [
        ("solved", "Solved"),
        ("not_solved", "Not solved"),
        ("partial", "Partly correct"),
        ("skipped", "Skipped"),
    ]
    SKIP_REASON_CHOICES = [
        ("absent", "Absent"),
        ("not_ready", "Not ready"),
        ("other", "Other"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    average_at_selection = models.FloatField()
    board_bonus_at_selection = models.FloatField(default=0)
    priority_level = models.CharField(max_length=20)
    selected_at = models.DateTimeField(auto_now_add=True)
    class_session = models.ForeignKey(ClassSession, null=True, blank=True, on_delete=models.SET_NULL)
    outcome = models.CharField(max_length=12, choices=OUTCOME_CHOICES, blank=True, default="")
    skip_reason = models.CharField(max_length=12, choices=SKIP_REASON_CHOICES, blank=True, default="")
    points = models.SmallIntegerField(default=0)
    teacher_comment = models.CharField(max_length=200, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.SET_NULL)
    student_answer = models.CharField(max_length=300, blank=True, default="")
    auto_checked = models.BooleanField(default=False)
    is_retry = models.BooleanField(default=False)
    retry = models.ForeignKey("Retry", null=True, blank=True, on_delete=models.SET_NULL, related_name="attempt_selections")

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name}"


class Retry(models.Model):
    STATUS_OPEN, STATUS_RESOLVED, STATUS_EXPIRED = "open", "resolved", "expired"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_EXPIRED, "Expired"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    question_wrong = models.ForeignKey(Question, null=True, blank=True, on_delete=models.SET_NULL, related_name="wrong_retries")
    created_in_session = models.ForeignKey(ClassSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="retries_created")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_selection = models.ForeignKey(
        BoardSelection, null=True, blank=True, on_delete=models.SET_NULL, related_name="resolves_retry"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    wrong_attempts = models.PositiveSmallIntegerField(default=1)
    origin_selection = models.ForeignKey(
        BoardSelection, null=True, blank=True, on_delete=models.SET_NULL, related_name="originated_retries"
    )

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} ({self.status})"