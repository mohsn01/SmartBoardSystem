from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("board/", views.teacher_board, name="board_teacher"),
    path("board/action/", views.teacher_action, name="board_teacher_action"),
    path("board/display/", views.board_display, name="board_display"),
    path("board/display/status/", views.board_display_status, name="board_display_status"),
    path("selection-history/", views.selection_history, name="selection_history"),
    path("progress-report/", views.progress_report, name="progress_report"),
    path("reports/", views.reports_dashboard, name="reports_dashboard"),
]