from django.contrib import admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import Mark, MarkHistory
from students.models import Student
from subjects.models import Subject


class MarkResource(resources.ModelResource):
    student = fields.Field(
        column_name='student_id',
        attribute='student',
        widget=ForeignKeyWidget(Student, 'student_id')
    )

    subject = fields.Field(
        column_name='subject_name',
        attribute='subject',
        widget=ForeignKeyWidget(Subject, 'name')
    )

    class Meta:
        model = Mark
        fields = ('student', 'subject', 'exam_mark', 'homework_mark')
        import_id_fields = ('student', 'subject')

    def do_instance_save(self, instance, is_create):
        instance.save(source="import")


@admin.register(Mark)
class MarkAdmin(ImportExportModelAdmin):
    resource_class = MarkResource
    list_display = ('student', 'subject', 'exam_mark', 'homework_mark', 'average')


@admin.register(MarkHistory)
class MarkHistoryAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'exam_mark', 'homework_mark', 'average', 'source', 'recorded_at')
    list_filter = ('subject', 'source')
    search_fields = ('student__full_name', 'subject__name')