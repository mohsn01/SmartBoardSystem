from django.contrib import admin
from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import Question, Subject, Topic, TopicScore
from students.models import Student


@admin.register(Subject)
class SubjectAdmin(ImportExportModelAdmin):
    pass


class TopicResource(resources.ModelResource):
    subject = fields.Field(
        column_name="subject_name",
        attribute="subject",
        widget=ForeignKeyWidget(Subject, "name")
    )
    name = fields.Field(column_name="topic_name", attribute="name")

    class Meta:
        model = Topic
        fields = ("subject", "name", "order")
        import_id_fields = ("subject", "name")


@admin.register(Topic)
class TopicAdmin(ImportExportModelAdmin):
    resource_class = TopicResource
    list_display = ("subject", "name", "order")
    list_filter = ("subject",)


class TopicWidget(ForeignKeyWidget):
    """Looks up a Topic by (subject_name, topic_name) since topic names repeat across subjects."""

    def clean(self, value, row=None, **kwargs):
        subject_name = row.get("subject_name") if row else None
        return Topic.objects.get(subject__name=subject_name, name=value)


class TopicScoreResource(resources.ModelResource):
    student = fields.Field(
        column_name="student_id",
        attribute="student",
        widget=ForeignKeyWidget(Student, "student_id")
    )
    topic = fields.Field(
        column_name="topic_name",
        attribute="topic",
        widget=TopicWidget(Topic, "name")
    )

    class Meta:
        model = TopicScore
        fields = ("student", "topic", "score")
        import_id_fields = ("student", "topic")


@admin.register(TopicScore)
class TopicScoreAdmin(ImportExportModelAdmin):
    resource_class = TopicScoreResource
    list_display = ("student", "topic", "score", "recorded_at")
    list_filter = ("topic__subject",)


class ChoicesWidget(widgets.Widget):
    """Pipe-separated choices in the CSV <-> a JSON list on the model."""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return []
        return [choice.strip() for choice in str(value).split("|") if choice.strip()]

    def render(self, value, obj=None):
        return "|".join(value or [])


class QuestionResource(resources.ModelResource):
    subject = fields.Field(
        column_name="subject_name",
        attribute="subject",
        widget=ForeignKeyWidget(Subject, "name")
    )
    topic = fields.Field(
        column_name="topic_name",
        attribute="topic",
        widget=TopicWidget(Topic, "name")
    )
    choices = fields.Field(
        column_name="choices",
        attribute="choices",
        widget=ChoicesWidget()
    )

    class Meta:
        model = Question
        fields = ("subject", "topic", "text", "answer", "answer_type", "choices", "difficulty", "explanation")
        import_id_fields = ()
        clean_model_instances = True

    def before_import_row(self, row, **kwargs):
        subject_name = row.get("subject_name")
        if subject_name and not Subject.objects.filter(name=subject_name).exists():
            raise ValueError(f"Unknown subject '{subject_name}'.")

        topic_name = row.get("topic_name")
        if topic_name and subject_name and not Topic.objects.filter(subject__name=subject_name, name=topic_name).exists():
            raise ValueError(f"Unknown topic '{topic_name}' for subject '{subject_name}'.")


@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    list_display = ("subject", "topic", "difficulty", "answer_type", "is_active", "text_preview")
    list_filter = ("subject", "difficulty", "answer_type", "is_active")
    search_fields = ("text", "answer")

    def text_preview(self, obj):
        return obj.text[:60]
    text_preview.short_description = "Question"