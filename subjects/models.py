from django.db import models


class Subject(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("subject", "name")
        ordering = ["subject", "order", "name"]

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class TopicScore(models.Model):
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    score = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.topic} ({self.score})"


class Question(models.Model):
    ANSWER_TYPE_CHOICES = [
        ("open", "Open (teacher judges)"),
        ("multiple_choice", "Multiple choice"),
        ("number", "Number"),
    ]
    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="questions")
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions")
    text = models.TextField()
    image = models.ImageField(upload_to="question_images/", blank=True, null=True)
    answer = models.CharField(max_length=300)
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPE_CHOICES, default="open")
    choices = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="medium")
    explanation = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="questions_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.answer_type == "multiple_choice":
            if not self.choices:
                raise ValidationError("Multiple choice questions need at least one choice.")
            if self.answer not in self.choices:
                raise ValidationError(
                    f"Answer '{self.answer}' must be one of the choices: {', '.join(self.choices)}."
                )

    def __str__(self):
        return f"{self.subject.name} - {self.text[:50]}"