from django.db import models


class Student(models.Model):
    full_name = models.CharField(max_length=200)
    student_id = models.CharField(max_length=50, unique=True)
    gender = models.CharField(max_length=10)
    classroom = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)

    def __str__(self):
        return self.full_name