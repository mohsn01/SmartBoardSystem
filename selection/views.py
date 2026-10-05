import random
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from students.models import Student
from subjects.models import Question, Subject, Topic
from marks.models import Mark
from .models import Attendance, BoardSelection, ClassSession, Retry
from . import config

ANSWERED_OUTCOMES = ("solved", "not_solved", "partial")
QUICK_TAGS = ["Needed a hint", "Careless mistake", "Concept gap", "Explained well", "Fast and confident"]
POINTS_BY_OUTCOME = {
    "solved": config.POINTS_SOLVED,
    "partial": config.POINTS_PARTIAL,
    "not_solved": config.POINTS_NOT_SOLVED,
}

def get_priority(average):
    if average < 50:
        return "High"
    elif average < 80:
        return "Medium"
    return "Low"


def get_weight(average):
    if average < 50:
        return 5
    elif average < 80:
        return 3
    return 1

def get_status(average):
    if average < 50:
        return "Weak Student"
    elif average < 80:
        return "Average Student"
    return "Excellent Student"


def get_fairness_multiplier(student, subject_id):
    """Down-weights students called on recently/often; up-weights those rarely/never called.
    Skipped calls never happened as far as fairness is concerned, so they're excluded."""
    history = BoardSelection.objects.filter(student=student, subject_id=subject_id).exclude(outcome="skipped")
    times_selected = history.count()
    last = history.order_by("-selected_at").first()

    if last is None:
        recency_factor = 1.0
    else:
        days_since = (timezone.now() - last.selected_at).days
        recency_factor = min(1.0, days_since / config.RECENCY_WINDOW_DAYS)

    frequency_factor = 1 / (1 + times_selected)
    return 0.5 + (recency_factor + frequency_factor) / 2


def get_board_bonus(student, subject_id):
    """How much board performance shifts a student's effective score, capped both ways.
    Doesn't touch the official Mark — see config.py for the per-event amounts."""
    resolved_retries = Retry.objects.filter(
        student=student, subject_id=subject_id, status=Retry.STATUS_RESOLVED
    ).count()
    open_retries = Retry.objects.filter(
        student=student, subject_id=subject_id, status=Retry.STATUS_OPEN
    ).count()
    correct_first_try = BoardSelection.objects.filter(
        student=student, subject_id=subject_id, outcome="solved", is_retry=False
    ).count()

    bonus = (
        resolved_retries * config.BOARD_BONUS_PER_RESOLVED_RETRY
        + correct_first_try * config.BOARD_BONUS_PER_CORRECT_FIRST_TRY
        + open_retries * config.BOARD_BONUS_PER_OPEN_RETRY
    )
    return max(config.BOARD_BONUS_MIN, min(config.BOARD_BONUS_MAX, bonus))


def get_retry_boost(student, subject_id, active_session_id):
    """An open retry from an earlier class pulls the student back in for another shot.
    Never boosts in the same class where they got it wrong — the retry comes in a later class."""
    has_open_retry = Retry.objects.filter(
        student=student, subject_id=subject_id, status=Retry.STATUS_OPEN
    ).exclude(created_in_session_id=active_session_id).exists()
    return config.RETRY_BOOST_MULTIPLIER if has_open_retry else 1.0


def _propose_candidate(subject_id, classroom, exclude_ids=None, active_session_id=None):
    """Picks a fairness-weighted candidate without persisting anything.
    Returns (mark, priority, status, candidate_names, board_bonus) or None."""
    exclude_ids = exclude_ids or []

    marks = Mark.objects.filter(
        subject_id=subject_id,
        student__classroom=classroom
    ).exclude(student_id__in=exclude_ids).select_related("student", "subject")

    if not marks.exists():
        return None

    weighted_marks = []
    candidate_names = []
    bonuses = {}
    for mark in marks:
        bonus = get_board_bonus(mark.student, subject_id)
        bonuses[mark.student_id] = bonus
        effective_score = mark.average + bonus
        final_weight = max(1, round(
            get_weight(effective_score)
            * get_fairness_multiplier(mark.student, subject_id)
            * get_retry_boost(mark.student, subject_id, active_session_id)
        ))
        weighted_marks.extend([mark] * final_weight)
        candidate_names.append(mark.student.full_name)

    selected_mark = random.choice(weighted_marks)
    board_bonus = bonuses[selected_mark.student_id]
    effective_score = selected_mark.average + board_bonus
    priority = get_priority(effective_score)
    status = get_status(effective_score)
    return selected_mark, priority, status, candidate_names[:15], board_bonus


def _get_active_session():
    return ClassSession.objects.filter(ended_at__isnull=True).first()


def _clear_current_candidate(session):
    session.current_student = None
    session.current_average = None
    session.current_priority = ""
    session.current_status = ""
    session.candidate_names = []
    session.skipped_ids = []


def _excluded_student_ids(active):
    """Students who already answered for real this session, plus anyone marked absent.
    A 'skipped' call (not_ready/other) does NOT exclude the student — they can be drawn again later."""
    answered = BoardSelection.objects.filter(
        class_session=active, outcome__in=ANSWERED_OUTCOMES
    ).values_list("student_id", flat=True)
    absent = Attendance.objects.filter(
        class_session=active, status=Attendance.STATUS_ABSENT
    ).values_list("student_id", flat=True)
    return list(set(answered) | set(absent))


def teacher_board(request):
    subjects = Subject.objects.all()
    classrooms = Student.objects.values_list("classroom", flat=True).distinct()
    all_topics = Topic.objects.select_related("subject").all()
    active = _get_active_session()

    context = {
        "subjects": subjects,
        "classrooms": classrooms,
        "all_topics": all_topics,
        "active": active,
        "quick_tags": QUICK_TAGS,
        "session_version": f"{active.id}-{active.updated_at.isoformat()}" if active else None,
    }

    if active and active.state == ClassSession.STATE_ATTENDANCE:
        context["roster"] = Student.objects.filter(classroom=active.classroom).order_by("full_name")

    if active and active.state == ClassSession.STATE_CONFIRMED:
        confirmed_selection = BoardSelection.objects.filter(
            class_session=active, student=active.current_student
        ).order_by("-selected_at").first()
        context["confirmed_selection"] = confirmed_selection
        if active.current_student_id:
            context["selection_count"] = BoardSelection.objects.filter(
                student=active.current_student
            ).count()

    return render(request, "selection/board_teacher.html", context)


def _call_next(active):
    """Proposes a fairness-weighted candidate and immediately commits it as a real BoardSelection."""
    exclude_ids = _excluded_student_ids(active)
    result = _propose_candidate(active.subject_id, active.classroom, exclude_ids, active.id)

    if not result:
        _clear_current_candidate(active)
        active.state = ClassSession.STATE_IDLE
        active.save()
        return False

    mark, priority, status, candidate_names, board_bonus = result

    open_retry = Retry.objects.filter(
        student=mark.student, subject_id=active.subject_id, status=Retry.STATUS_OPEN
    ).exclude(created_in_session=active).order_by("created_at").first()

    BoardSelection.objects.create(
        student=mark.student,
        subject=mark.subject,
        topic=active.topic,
        average_at_selection=mark.average,
        board_bonus_at_selection=board_bonus,
        priority_level=priority,
        class_session=active,
        is_retry=bool(open_retry),
        retry=open_retry,
    )
    active.current_student = mark.student
    active.current_average = mark.average
    active.current_priority = priority
    active.current_status = status
    active.candidate_names = candidate_names
    active.skipped_ids = []
    active.state = ClassSession.STATE_CONFIRMED
    active.save()
    return True


def _pick_question(subject_id, topic_id, student, active, is_retry, open_retry):
    """Picks an active question for the subject (and topic, if the session has one).
    Avoids repeats where possible; a retry gets the same topic but a different question
    from the one the student got wrong."""
    qs = Question.objects.filter(subject_id=subject_id, is_active=True)
    if topic_id:
        qs = qs.filter(topic_id=topic_id)

    if is_retry and open_retry and open_retry.question_wrong_id:
        qs = qs.exclude(id=open_retry.question_wrong_id)

    if not qs.exists():
        return None

    asked_this_session = BoardSelection.objects.filter(
        class_session=active, question__isnull=False
    ).values_list("question_id", flat=True)
    asked_to_student = BoardSelection.objects.filter(
        student=student, question__isnull=False
    ).values_list("question_id", flat=True)

    fresh = qs.exclude(id__in=set(asked_this_session) | set(asked_to_student))
    pool = fresh if fresh.exists() else qs
    return pool.order_by("?").first()


def _record_outcome(board_selection, active, outcome, student_answer="", auto_checked=False):
    """Single place that applies the +1/0/-1 points rule and keeps Retry records in sync."""
    board_selection.outcome = outcome
    board_selection.points = POINTS_BY_OUTCOME.get(outcome, 0)
    board_selection.student_answer = student_answer
    board_selection.auto_checked = auto_checked
    board_selection.answered_at = timezone.now()

    if outcome == "solved" and board_selection.is_retry and board_selection.retry_id:
        retry = board_selection.retry
        retry.status = Retry.STATUS_RESOLVED
        retry.resolved_at = timezone.now()
        retry.resolved_by_selection = board_selection
        retry.save()
        if config.RETRY_REFUND and retry.origin_selection_id:
            origin = retry.origin_selection
            if origin.points < 0:
                origin.points = 0
                origin.save(update_fields=["points"])

    elif outcome == "not_solved":
        if board_selection.is_retry and board_selection.retry_id:
            retry = board_selection.retry
            retry.wrong_attempts += 1
            retry.save(update_fields=["wrong_attempts"])
        else:
            new_retry = Retry.objects.create(
                student=board_selection.student,
                subject=board_selection.subject,
                topic=board_selection.topic,
                question_wrong=board_selection.question,
                created_in_session=active,
                origin_selection=board_selection,
            )
            board_selection.retry = new_retry

    board_selection.save()
    active.save(update_fields=["updated_at"])


def teacher_action(request):
    if request.method != "POST":
        return redirect("board_teacher")

    action = request.POST.get("action")
    active = _get_active_session()

    if action == "start":
        if active:
            messages.warning(request, "Finish the current class before starting a new one.")
        else:
            subject_id = request.POST.get("subject")
            classroom = request.POST.get("classroom")
            topic_id = request.POST.get("topic") or None
            if subject_id and classroom:
                ClassSession.objects.create(
                    classroom=classroom,
                    subject_id=subject_id,
                    topic_id=topic_id,
                    state=ClassSession.STATE_ATTENDANCE,
                )
            else:
                messages.warning(request, "Choose a classroom and subject to start.")
        return redirect("board_teacher")

    if not active:
        return redirect("board_teacher")

    if action == "confirm_attendance":
        if active.state == ClassSession.STATE_ATTENDANCE:
            absent_ids = set(request.POST.getlist("absent"))
            roster = Student.objects.filter(classroom=active.classroom)
            for student in roster:
                status = (
                    Attendance.STATUS_ABSENT
                    if str(student.id) in absent_ids
                    else Attendance.STATUS_PRESENT
                )
                Attendance.objects.update_or_create(
                    class_session=active, student=student,
                    defaults={"status": status},
                )
            active.state = ClassSession.STATE_IDLE
            active.save()

    elif action == "call":
        if not _call_next(active):
            messages.info(request, "No more students left to call for this class and subject.")

    elif action == "skip":
        reason = request.POST.get("reason", "other")
        if reason not in ("absent", "not_ready", "other"):
            reason = "other"

        if active.current_student_id:
            current = BoardSelection.objects.filter(
                class_session=active, student=active.current_student, outcome=""
            ).order_by("-selected_at").first()
            if current:
                current.outcome = "skipped"
                current.skip_reason = reason
                current.answered_at = timezone.now()
                current.save()
            if reason == "absent":
                Attendance.objects.update_or_create(
                    class_session=active, student=active.current_student,
                    defaults={"status": Attendance.STATUS_ABSENT},
                )

        if not _call_next(active):
            messages.info(request, "No more students left to call for this class and subject.")

    elif action == "mark_outcome":
        outcome = request.POST.get("outcome")
        if outcome in ANSWERED_OUTCOMES and active.current_student_id:
            board_selection = BoardSelection.objects.filter(
                class_session=active, student=active.current_student
            ).order_by("-selected_at").first()
            if board_selection and not board_selection.outcome:
                _record_outcome(board_selection, active, outcome)

    elif action == "ask_again":
        # Keeps the same student at the board for another round instead of drawing someone new.
        if active.state == ClassSession.STATE_CONFIRMED and active.current_student_id:
            current = BoardSelection.objects.filter(
                class_session=active, student=active.current_student
            ).order_by("-selected_at").first()
            if current and current.outcome:
                student = active.current_student
                mark = Mark.objects.filter(student=student, subject_id=active.subject_id).first()
                if mark:
                    board_bonus = get_board_bonus(student, active.subject_id)
                    effective_score = mark.average + board_bonus
                    priority = get_priority(effective_score)
                    status = get_status(effective_score)
                    open_retry = Retry.objects.filter(
                        student=student, subject_id=active.subject_id, status=Retry.STATUS_OPEN
                    ).exclude(created_in_session=active).order_by("created_at").first()

                    BoardSelection.objects.create(
                        student=student,
                        subject=active.subject,
                        topic=active.topic,
                        average_at_selection=mark.average,
                        board_bonus_at_selection=board_bonus,
                        priority_level=priority,
                        class_session=active,
                        is_retry=bool(open_retry),
                        retry=open_retry,
                    )
                    active.current_average = mark.average
                    active.current_priority = priority
                    active.current_status = status
                    active.save()

    elif action == "ask_question":
        if active.state == ClassSession.STATE_CONFIRMED and active.current_student_id:
            board_selection = BoardSelection.objects.filter(
                class_session=active, student=active.current_student
            ).order_by("-selected_at").first()
            if board_selection and not board_selection.outcome and not board_selection.question_id:
                open_retry = board_selection.retry if board_selection.is_retry else None
                question = _pick_question(
                    active.subject_id, active.topic_id, active.current_student,
                    active, board_selection.is_retry, open_retry,
                )
                if question:
                    board_selection.question = question
                    board_selection.save(update_fields=["question"])
                    active.save(update_fields=["updated_at"])
                else:
                    messages.info(request, "No active questions for this subject/topic yet — add some in the admin.")

    elif action == "answer_question":
        if active.current_student_id:
            board_selection = BoardSelection.objects.filter(
                class_session=active, student=active.current_student
            ).order_by("-selected_at").first()
            if board_selection and board_selection.question_id and not board_selection.outcome:
                question = board_selection.question
                submitted = ""
                outcome = None

                if question.answer_type == "multiple_choice":
                    submitted = request.POST.get("choice", "")
                    outcome = "solved" if submitted.strip().lower() == question.answer.strip().lower() else "not_solved"
                elif question.answer_type == "number":
                    submitted = request.POST.get("number_answer", "")
                    try:
                        outcome = "solved" if abs(float(submitted) - float(question.answer)) < 1e-6 else "not_solved"
                    except (TypeError, ValueError):
                        outcome = None

                if outcome:
                    _record_outcome(board_selection, active, outcome, student_answer=submitted, auto_checked=True)

    elif action == "add_tag":
        tag = request.POST.get("tag")
        if tag and active.current_student_id:
            board_selection = BoardSelection.objects.filter(
                class_session=active, student=active.current_student
            ).order_by("-selected_at").first()
            if board_selection and board_selection.outcome:
                tags = list(board_selection.tags or [])
                if tag in tags:
                    tags.remove(tag)
                else:
                    tags.append(tag)
                board_selection.tags = tags
                board_selection.save()

    elif action == "finish":
        active.ended_at = timezone.now()
        active.state = ClassSession.STATE_IDLE
        _clear_current_candidate(active)
        active.save()

    return redirect("board_teacher")


def board_display(request):
    return render(request, "selection/board_display.html", {})


def board_display_status(request):
    active = _get_active_session()

    if not active:
        return JsonResponse({"active": False, "state": "idle", "version": "none", "student": None})

    data = {
        "active": True,
        "state": active.state,
        "version": f"{active.id}-{active.updated_at.isoformat()}",
        "student": None,
    }

    if active.current_student_id and active.state == ClassSession.STATE_CONFIRMED:
        student = active.current_student
        data["student"] = {
            "name": student.full_name,
            "student_id": student.student_id,
            "classroom": student.classroom,
            "photo_url": student.photo.url if student.photo else None,
        }
        data["candidate_names"] = active.candidate_names
        confirmed_selection = BoardSelection.objects.filter(
            class_session=active, student=active.current_student
        ).order_by("-selected_at").first()
        data["outcome_set"] = bool(confirmed_selection and confirmed_selection.outcome)

        if confirmed_selection and confirmed_selection.outcome:
            # Whether it was right/wrong is fine to show — that's the point of calling them up.
            # The point VALUE is only ever included when positive; a -1 never reaches this response.
            data["outcome"] = confirmed_selection.outcome
            if confirmed_selection.points > 0:
                data["points"] = confirmed_selection.points

        if confirmed_selection and confirmed_selection.question_id and not confirmed_selection.outcome:
            question = confirmed_selection.question
            data["question"] = {
                "id": question.id,
                "text": question.text,
                "image_url": question.image.url if question.image else None,
                "answer_type": question.answer_type,
                "choices": question.choices,
            }

    return JsonResponse(data)


def home(request):
    return render(request, "selection/home.html")

def selection_history(request):
    selections = BoardSelection.objects.select_related(
        "student", "subject"
    ).order_by("-selected_at")

    return render(request, "selection/selection_history.html", {
        "selections": selections
    })

def progress_report(request):
    selections = BoardSelection.objects.select_related(
        "student", "subject"
    ).order_by("-selected_at")

    progress_data = []

    for selection in selections:
        current_mark = Mark.objects.filter(
            student=selection.student,
            subject=selection.subject
        ).first()

        if current_mark:
            old_average = selection.average_at_selection
            current_average = current_mark.average
            difference = current_average - old_average

            if difference > 0:
                status = "Improved"
            elif difference < 0:
                status = "Decreased"
            else:
                status = "No Change"

            progress_data.append({
                "student": selection.student,
                "subject": selection.subject,
                "old_average": old_average,
                "current_average": current_average,
                "difference": difference,
                "status": status,
                "selected_at": selection.selected_at,
            })

    return render(request, "selection/progress_report.html", {
        "progress_data": progress_data
    })
def reports_dashboard(request):
    classroom = request.GET.get("classroom")
    search = request.GET.get("search")
    status = request.GET.get("status")

    marks = Mark.objects.select_related("student", "subject")

    if classroom:
        marks = marks.filter(student__classroom=classroom)

    if search:
        marks = marks.filter(student__full_name__icontains=search)

    if status == "weak":
        marks = marks.filter(average__lt=50)
    elif status == "average":
        marks = marks.filter(average__gte=50, average__lt=80)
    elif status == "excellent":
        marks = marks.filter(average__gte=80)

    classrooms = Student.objects.values_list("classroom", flat=True).distinct()

    filtered_students = Student.objects.filter(
        id__in=marks.values_list("student_id", flat=True)
    ).distinct()

    filtered_subjects = Subject.objects.filter(
        id__in=marks.values_list("subject_id", flat=True)
    ).distinct()

    filtered_selections = BoardSelection.objects.select_related("student", "subject")

    if classroom:
        filtered_selections = filtered_selections.filter(student__classroom=classroom)

    if search:
        filtered_selections = filtered_selections.filter(student__full_name__icontains=search)

    total_students = filtered_students.count()
    total_subjects = filtered_subjects.count()
    total_marks = marks.count()
    total_selections = filtered_selections.count()

    weak_count = marks.filter(average__lt=50).count()
    average_count = marks.filter(average__gte=50, average__lt=80).count()
    excellent_count = marks.filter(average__gte=80).count()

    improved_count = 0
    decreased_count = 0
    no_change_count = 0

    for selection in filtered_selections:
        current_mark = Mark.objects.filter(
            student=selection.student,
            subject=selection.subject
        ).first()

        if current_mark:
            if current_mark.average > selection.average_at_selection:
                improved_count += 1
            elif current_mark.average < selection.average_at_selection:
                decreased_count += 1
            else:
                no_change_count += 1

    return render(request, "selection/reports.html", {
        "total_students": total_students,
        "total_subjects": total_subjects,
        "total_marks": total_marks,
        "total_selections": total_selections,
        "weak_students": weak_count,
        "improved_count": improved_count,
        "decreased_count": decreased_count,
        "no_change_count": no_change_count,
        "weak_count": weak_count,
        "average_count": average_count,
        "excellent_count": excellent_count,
        "classrooms": classrooms,
        "marks": marks[:50],
    })
