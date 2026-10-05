from django.contrib import admin
from .models import BoardSelection, ClassSession, Attendance, Retry


@admin.register(BoardSelection)
class BoardSelectionAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'topic', 'average_at_selection', 'priority_level', 'outcome', 'skip_reason', 'points', 'question', 'is_retry', 'selected_at')
    list_filter = ('subject', 'priority_level', 'outcome', 'is_retry', 'selected_at')
    search_fields = ('student__full_name', 'subject__name')


@admin.register(Retry)
class RetryAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'topic', 'status', 'wrong_attempts', 'created_at', 'resolved_at')
    list_filter = ('subject', 'status')
    search_fields = ('student__full_name',)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'subject', 'topic', 'state', 'current_student', 'started_at', 'ended_at')
    list_filter = ('subject', 'state')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_session', 'status', 'marked_at')
    list_filter = ('status',)
    search_fields = ('student__full_name',)