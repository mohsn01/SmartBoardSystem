from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from .models import Student


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    list_display = ('full_name', 'student_id', 'gender', 'classroom', 'photo_preview')
    readonly_fields = ('photo_preview',)

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:cover;border-radius:6px;">',
                obj.photo.url,
            )
        return "—"
    photo_preview.short_description = "Photo"