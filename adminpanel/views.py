from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
import calendar
import json
from django.db.models import Sum, Count, Avg
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import user_passes_test

from app1.models import *
from app1.serializers import QuestionSerializer, QuizSerializer


def _is_admin_user(user):
    return user.is_authenticated and user.is_staff


admin_login_required = user_passes_test(_is_admin_user, login_url='admin_login')


def _calculate_growth(series):
    if len(series) < 2:
        return 0

    current = series[-1]
    previous = series[-2]

    if previous > 0:
        return round(((current - previous) / previous) * 100, 1)

    return 100 if current > 0 else 0


def _get_registration_date_field():
    registration_field_names = {field.name for field in Registration._meta.get_fields()}

    for candidate in ("created_at", "otp_created_at"):
        if candidate in registration_field_names:
            return candidate

    return None


def _format_serializer_errors(errors):
    messages = []

    if isinstance(errors, dict):
        for field, value in errors.items():
            if isinstance(value, (list, tuple)):
                rendered = ", ".join(str(item) for item in value)
            else:
                rendered = str(value)
            messages.append(f"{field}: {rendered}")
    elif isinstance(errors, list):
        messages.extend(str(item) for item in errors)
    else:
        messages.append(str(errors))

    return " ".join(messages)


def admin_login(request):
    if _is_admin_user(request.user):
        return redirect('dashboard_home')

    context = {}

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user and user.is_staff:
            auth_login(request, user)
            return redirect('dashboard_home')

        context["error"] = "Invalid admin username or password."

    return render(request, "adminpanel/login.html", context)


def admin_logout(request):
    auth_logout(request)
    return redirect('admin_login')


@admin_login_required
def dashboard_home(request):

    # ===============================
    # BASIC COUNTS
    # ===============================

    total_courses = Course.objects.count()
    total_students = Registration.objects.count()
    total_enrollments = Enrollment.objects.count()
    total_reviews = Review.objects.count()

    total_quizzes = Quiz.objects.count()
    total_results = Result.objects.count()
    total_comments = Comment.objects.count()
    recent_enrollments = Enrollment.objects.select_related('user', 'course').order_by('-enrolled_at')[:6]
    # Review does not currently have a created_at field, so use descending id as
    # the best available proxy for newest feedback.
    recent_reviews = Review.objects.select_related('user', 'course').order_by('-id')[:4]


    # ===============================
    # REVENUE FROM ENROLLMENTS
    # ===============================

    total_revenue = Payment.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0


    # ===============================
    # LEVEL DISTRIBUTION
    # ===============================

    beginner_courses = Course.objects.filter(level='beginner').count()
    intermediate_courses = Course.objects.filter(level='intermediate').count()
    advanced_courses = Course.objects.filter(level='advanced').count()


    # ===============================
    # LAST 12 MONTHS ENROLLMENT DATA
    # ===============================

    now = timezone.now()

    chart_labels = []
    monthly_enrollments = []
    monthly_students = []
    monthly_revenue = []
    monthly_courses = []
    registration_date_field = _get_registration_date_field()

    for i in range(11, -1, -1):

        year = now.year
        month = now.month - i

        while month <= 0:
            month += 12
            year -= 1

        chart_labels.append(calendar.month_abbr[month])

        # enrollments per month
        enroll_count = Enrollment.objects.filter(
            enrolled_at__year=year,
            enrolled_at__month=month
        ).count()

        monthly_enrollments.append(enroll_count)

        # Registration does not currently have a created_at field,
        # so fall back to the first available datetime field.
        if registration_date_field:
            student_count = Registration.objects.filter(
                **{
                    f"{registration_date_field}__year": year,
                    f"{registration_date_field}__month": month,
                }
            ).count()
        else:
            student_count = 0

        monthly_students.append(student_count)

        revenue_total = Payment.objects.filter(
            created_at__year=year,
            created_at__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_revenue.append(revenue_total)

        course_count = Course.objects.filter(
            created_at__year=year,
            created_at__month=month
        ).count()
        monthly_courses.append(course_count)


    # ===============================
    # MONTHLY GROWTH
    # ===============================

    student_growth = _calculate_growth(monthly_students)
    enrollment_growth = _calculate_growth(monthly_enrollments)
    revenue_growth = _calculate_growth(monthly_revenue)
    course_growth = _calculate_growth(monthly_courses)


    # ===============================
    # CONTEXT
    # ===============================

    context = {

        # main stats
        'total_courses': total_courses,
        'total_students': total_students,
        'total_enrollments': total_enrollments,
        'total_reviews': total_reviews,
        'total_revenue': total_revenue,

        # extra stats
        'total_quizzes': total_quizzes,
        'total_results': total_results,
        'total_comments': total_comments,
        'recent_enrollments': recent_enrollments,
        'recent_reviews': recent_reviews,

        # level distribution
        'beginner_courses': beginner_courses,
        'intermediate_courses': intermediate_courses,
        'advanced_courses': advanced_courses,

        # charts
        'chart_labels': chart_labels,
        'monthly_enrollments': monthly_enrollments,
        'monthly_students': monthly_students,
        'monthly_revenue': monthly_revenue,
        'monthly_courses': monthly_courses,

        # growth
        'student_growth': student_growth,
        'enrollment_growth': enrollment_growth,
        'revenue_growth': revenue_growth,
        'course_growth': course_growth,
    }

    return render(request, 'adminpanel/dashboard.html', context)


@admin_login_required
def students_manage(request):
    action = request.GET.get("action")
    pk = request.GET.get("pk")

    if action == "delete" and pk:
        student = get_object_or_404(Registration, pk=pk)
        student.delete()
        return redirect("students_manage")

    student_instance = None
    if action == "edit" and pk:
        student_instance = get_object_or_404(Registration, pk=pk)

    form_error = None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        mobile = request.POST.get("mobile", "").strip()
        level = request.POST.get("level", "beginner")
        password = request.POST.get("password", "")

        duplicate_email_qs = Registration.objects.filter(email=email)
        if student_instance:
            duplicate_email_qs = duplicate_email_qs.exclude(pk=student_instance.pk)

        if duplicate_email_qs.exists():
            form_error = "A student with this email already exists."
        elif not student_instance and not password:
            form_error = "Password is required when adding a new student."
        else:
            if student_instance:
                student_instance.name = name
                student_instance.email = email
                student_instance.mobile = mobile
                student_instance.level = level
                if password:
                    student_instance.password = password
                student_instance.save()
            else:
                Registration.objects.create(
                    name=name,
                    email=email,
                    mobile=mobile,
                    password=password,
                    level=level,
                )

            return redirect("students_manage")

    registration_date_field = _get_registration_date_field()
    order_by = [f"-{registration_date_field}", "name"] if registration_date_field else ["name"]

    students = list(Registration.objects.all().order_by(*order_by))

    enrollment_totals = {
        row["user"]: row["total"]
        for row in Enrollment.objects.values("user").annotate(total=Count("id"))
    }
    review_totals = {
        row["user"]: row["total"]
        for row in Review.objects.values("user").annotate(total=Count("id"))
    }
    favourite_totals = {
        row["user"]: row["total"]
        for row in Favourite.objects.values("user").annotate(total=Count("id"))
    }
    payment_totals = {
        row["user"]: row["total"] or 0
        for row in Payment.objects.values("user").annotate(total=Sum("amount"))
    }

    level_labels = dict(Registration.LEVEL_CHOICES)
    level_totals = {level: 0 for level in level_labels}
    active_learners = 0
    total_enrollments = 0
    total_revenue = 0
    joined_students = 0

    for student in students:
        student.enrollment_total = enrollment_totals.get(student.id, 0)
        student.review_total = review_totals.get(student.id, 0)
        student.favourite_total = favourite_totals.get(student.id, 0)
        student.total_spent = payment_totals.get(student.id, 0)
        student.joined_at = getattr(student, registration_date_field, None) if registration_date_field else None
        student.level_label = level_labels.get(student.level, student.level.title())

        total_enrollments += student.enrollment_total
        total_revenue += student.total_spent
        level_totals[student.level] = level_totals.get(student.level, 0) + 1

        if student.enrollment_total:
            active_learners += 1

        if student.joined_at:
            joined_students += 1

    total_students = len(students)
    average_courses = round(total_enrollments / total_students, 1) if total_students else 0

    level_breakdown = []
    for level, label in Registration.LEVEL_CHOICES:
        total = level_totals.get(level, 0)
        percentage = round((total / total_students) * 100) if total_students else 0
        level_breakdown.append({
            "code": level,
            "label": label,
            "total": total,
            "percentage": percentage,
        })

    top_students = sorted(
        sorted(students, key=lambda student: student.name.lower()),
        key=lambda student: (
            student.enrollment_total,
            student.total_spent,
            student.review_total,
        ),
        reverse=True,
    )[:3]

    context = {
        "students": students,
        "top_students": top_students,
        "level_breakdown": level_breakdown,
        "total_students": total_students,
        "active_learners": active_learners,
        "total_enrollments": total_enrollments,
        "total_revenue": total_revenue,
        "joined_students": joined_students,
        "average_courses": average_courses,
        "edit_mode": student_instance,
        "student": student_instance,
        "form_error": form_error,
    }

    return render(request, "adminpanel/students_manage.html", context)


@admin_login_required
def enrollments_manage(request):
    action = request.GET.get("action")
    pk = request.GET.get("pk")

    if action == "delete" and pk:
        enrollment = get_object_or_404(Enrollment, pk=pk)
        enrollment.delete()
        return redirect("enrollments_manage")

    enrollments = list(
        Enrollment.objects.select_related("user", "course").order_by("-enrolled_at")
    )

    payment_totals = {
        (row["user"], row["course"]): row["total"] or 0
        for row in Payment.objects.values("user", "course").annotate(total=Sum("amount"))
    }

    level_labels = dict(Course.LEVEL_CHOICES)
    level_totals = {level: 0 for level in level_labels}
    total_revenue = 0
    unique_students = set()
    course_rollup = {}

    for enrollment in enrollments:
        enrollment.payment_total = payment_totals.get(
            (enrollment.user_id, enrollment.course_id),
            0,
        )
        enrollment.level_code = enrollment.course.level
        enrollment.level_label = level_labels.get(
            enrollment.course.level,
            enrollment.course.level.title(),
        )
        total_revenue += enrollment.payment_total
        unique_students.add(enrollment.user_id)
        level_totals[enrollment.course.level] = level_totals.get(enrollment.course.level, 0) + 1

        course_entry = course_rollup.setdefault(
            enrollment.course_id,
            {
                "name": enrollment.course.name,
                "level_label": enrollment.level_label,
                "count": 0,
                "revenue": 0,
            },
        )
        course_entry["count"] += 1
        course_entry["revenue"] += enrollment.payment_total

    total_enrollments = len(enrollments)
    active_students = len(unique_students)
    active_courses = len(course_rollup)
    average_order_value = round(total_revenue / total_enrollments) if total_enrollments else 0

    level_breakdown = []
    for level, label in Course.LEVEL_CHOICES:
        total = level_totals.get(level, 0)
        percentage = round((total / total_enrollments) * 100) if total_enrollments else 0
        level_breakdown.append({
            "code": level,
            "label": label,
            "total": total,
            "percentage": percentage,
        })

    top_courses = sorted(
        course_rollup.values(),
        key=lambda item: (item["count"], item["revenue"], item["name"].lower()),
        reverse=True,
    )[:4]

    context = {
        "enrollments": enrollments,
        "total_enrollments": total_enrollments,
        "active_students": active_students,
        "active_courses": active_courses,
        "total_revenue": total_revenue,
        "average_order_value": average_order_value,
        "level_breakdown": level_breakdown,
        "top_courses": top_courses,
    }

    return render(request, "adminpanel/enrollments_manage.html", context)


@admin_login_required
def quiz_manage(request):
    action = request.GET.get("action")
    pk = request.GET.get("pk")
    form_error = None
    selected_course_id = ""
    quiz_name = ""
    json_payload = json.dumps(
        [
            {
                "question_text": "What does HTML stand for?",
                "option1": "Hyper Text Markup Language",
                "option2": "High Transfer Machine Language",
                "option3": "Home Tool Markup Language",
                "option4": "Hyperlink Text Machine Language",
                "correct_option": 1,
            }
        ],
        indent=2,
    )

    if action == "delete" and pk:
        quiz = get_object_or_404(Quiz, pk=pk)
        quiz.delete()
        return redirect("quiz_manage")

    if request.method == "POST":
        selected_course_id = request.POST.get("course", "").strip()
        quiz_name = request.POST.get("title", "").strip()
        json_payload = request.POST.get("json_payload", "").strip()

        if not selected_course_id:
            form_error = "Choose a course before uploading quiz JSON."
        elif not json_payload:
            form_error = "Quiz JSON is required."
        else:
            course = get_object_or_404(Course, pk=selected_course_id)

            try:
                raw_payload = json.loads(json_payload)
            except json.JSONDecodeError as exc:
                form_error = f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            else:
                title = ""
                questions_payload = raw_payload

                if isinstance(raw_payload, dict):
                    if "questions" in raw_payload:
                        questions_payload = raw_payload.get("questions")
                    payload_title = str(raw_payload.get("title", "")).strip()
                    if payload_title:
                        title = payload_title

                if quiz_name:
                    title = quiz_name

                if not isinstance(questions_payload, list):
                    questions_payload = [questions_payload]

                if not title:
                    next_count = Quiz.objects.filter(course=course).count() + 1
                    title = f"{course.name} Quiz {next_count}"

                serializer = QuizSerializer(data={
                    "course": course.id,
                    "title": title,
                    "questions": questions_payload,
                })

                if serializer.is_valid():
                    serializer.save()
                    return redirect("quiz_manage")

                form_error = _format_serializer_errors(serializer.errors)

    quizzes = list(
        Quiz.objects.select_related("course").order_by("course__name", "title")
    )
    courses = Course.objects.filter(is_active=True).order_by("name")

    question_totals = {
        row["quiz"]: row["total"]
        for row in Question.objects.values("quiz").annotate(total=Count("id"))
    }
    result_rows = {
        row["quiz"]: row
        for row in Result.objects.values("quiz").annotate(
            total_attempts=Count("id"),
            average_score=Avg("score"),
            average_total=Avg("total"),
        )
    }

    level_totals = {level: 0 for level, _ in Course.LEVEL_CHOICES}
    total_questions = 0
    total_attempts = 0
    scored_quizzes = 0
    overall_percentage = 0

    for quiz in quizzes:
        quiz.question_total = question_totals.get(quiz.id, 0)
        quiz.level_code = quiz.course.level
        quiz.level_label = dict(Course.LEVEL_CHOICES).get(
            quiz.course.level,
            quiz.course.level.title(),
        )

        result_row = result_rows.get(quiz.id, {})
        quiz.attempt_total = result_row.get("total_attempts", 0)
        average_score = result_row.get("average_score") or 0
        average_total = result_row.get("average_total") or 0
        quiz.average_percentage = round((average_score / average_total) * 100, 1) if average_total else 0

        total_questions += quiz.question_total
        total_attempts += quiz.attempt_total
        level_totals[quiz.level_code] = level_totals.get(quiz.level_code, 0) + 1

        if quiz.attempt_total:
            scored_quizzes += 1
            overall_percentage += quiz.average_percentage

    total_quizzes = len(quizzes)
    active_quizzes = sum(1 for quiz in quizzes if quiz.attempt_total)
    average_percentage = round(overall_percentage / scored_quizzes, 1) if scored_quizzes else 0

    level_breakdown = []
    for level, label in Course.LEVEL_CHOICES:
        total = level_totals.get(level, 0)
        percentage = round((total / total_quizzes) * 100) if total_quizzes else 0
        level_breakdown.append({
            "code": level,
            "label": label,
            "total": total,
            "percentage": percentage,
        })

    context = {
        "quizzes": quizzes,
        "total_quizzes": total_quizzes,
        "total_questions": total_questions,
        "total_attempts": total_attempts,
        "active_quizzes": active_quizzes,
        "average_percentage": average_percentage,
        "level_breakdown": level_breakdown,
        "courses": courses,
        "quiz_form_error": form_error,
        "selected_course_id": selected_course_id,
        "quiz_name": quiz_name,
        "json_payload": json_payload,
        "sample_payload": json.dumps(
            {
                "questions": [
                    {
                        "question_text": "What does HTML stand for?",
                        "option1": "Hyper Text Markup Language",
                        "option2": "High Transfer Machine Language",
                        "option3": "Home Tool Markup Language",
                        "option4": "Hyperlink Text Machine Language",
                        "correct_option": 1,
                    }
                ]
            },
            indent=2,
        ),
    }

    return render(request, "adminpanel/quiz_manage.html", context)


@admin_login_required
def quiz_questions_manage(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.select_related("course"), pk=quiz_id)

    action = request.GET.get("action")
    pk = request.GET.get("pk")
    question_instance = None

    if action == "delete" and pk:
        question = get_object_or_404(Question, pk=pk, quiz=quiz)
        question.delete()
        return redirect("quiz_questions_manage", quiz_id=quiz.id)

    if action == "edit" and pk:
        question_instance = get_object_or_404(Question, pk=pk, quiz=quiz)

    form_error = None
    payload_text = ""

    if question_instance:
        payload_text = json.dumps(
            {
                "question_text": question_instance.question_text,
                "option1": question_instance.option1,
                "option2": question_instance.option2,
                "option3": question_instance.option3,
                "option4": question_instance.option4,
                "correct_option": question_instance.correct_option,
            },
            indent=2,
        )

    if request.method == "POST":
        if not question_instance:
            form_error = "Add new quiz JSON from the Quiz Management page."
        else:
            payload_text = request.POST.get("json_payload", "").strip()

            if not payload_text:
                form_error = "JSON payload is required."
            else:
                try:
                    raw_payload = json.loads(payload_text)
                except json.JSONDecodeError as exc:
                    form_error = f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
                else:
                    normalized_payload = raw_payload

                    if isinstance(raw_payload, dict) and "questions" in raw_payload:
                        payload_course = str(raw_payload.get("course", "")).strip()
                        payload_title = str(raw_payload.get("title", "")).strip()

                        if payload_course and payload_course != str(quiz.course_id):
                            form_error = "JSON course does not match the current quiz course."
                        elif payload_title and payload_title != quiz.title:
                            form_error = "JSON title does not match the current quiz title."
                        else:
                            normalized_payload = raw_payload.get("questions")

                    if not form_error:
                        if isinstance(normalized_payload, list):
                            form_error = "Edit mode accepts a single question object only."
                        else:
                            serializer = QuestionSerializer(question_instance, data=normalized_payload)
                            if serializer.is_valid():
                                serializer.save()
                                return redirect("quiz_questions_manage", quiz_id=quiz.id)
                            form_error = _format_serializer_errors(serializer.errors)

    questions = list(Question.objects.filter(quiz=quiz).order_by("id"))
    attempt_total = Result.objects.filter(quiz=quiz).count()
    average_result = Result.objects.filter(quiz=quiz).aggregate(
        average_score=Avg("score"),
        average_total=Avg("total"),
    )
    average_total = average_result["average_total"] or 0
    average_percentage = round(((average_result["average_score"] or 0) / average_total) * 100, 1) if average_total else 0

    for index, question in enumerate(questions, start=1):
        question.item_number = index
        question.correct_option_value = getattr(question, f"option{question.correct_option}")

    context = {
        "quiz": quiz,
        "questions": questions,
        "question": question_instance,
        "edit_mode": question_instance,
        "form_error": form_error,
        "payload_text": payload_text,
        "total_questions": len(questions),
        "attempt_total": attempt_total,
        "average_percentage": average_percentage,
    }

    return render(request, "adminpanel/quiz_questions_manage.html", context)


@admin_login_required
def results_manage(request):
    action = request.GET.get("action")
    pk = request.GET.get("pk")

    if action == "delete" and pk:
        result = get_object_or_404(Result, pk=pk)
        result.delete()
        return redirect("results_manage")

    results = list(
        Result.objects.select_related("quiz", "quiz__course").order_by("-submitted_at")
    )

    level_totals = {level: 0 for level, _ in Course.LEVEL_CHOICES}
    total_attempts = len(results)
    passed_attempts = 0
    total_percentage = 0
    learner_totals = {}

    for result in results:
        result.level_code = result.quiz.course.level
        result.level_label = dict(Course.LEVEL_CHOICES).get(
            result.level_code,
            result.level_code.title(),
        )
        result.percentage = round((result.score / result.total) * 100, 1) if result.total else 0
        result.passed = result.percentage >= 70

        total_percentage += result.percentage
        if result.passed:
            passed_attempts += 1

        level_totals[result.level_code] = level_totals.get(result.level_code, 0) + 1
        learner_totals[result.user_email] = learner_totals.get(result.user_email, 0) + 1

    average_percentage = round(total_percentage / total_attempts, 1) if total_attempts else 0
    unique_learners = len(learner_totals)
    pass_rate = round((passed_attempts / total_attempts) * 100) if total_attempts else 0

    level_breakdown = []
    for level, label in Course.LEVEL_CHOICES:
        total = level_totals.get(level, 0)
        percentage = round((total / total_attempts) * 100) if total_attempts else 0
        level_breakdown.append({
            "code": level,
            "label": label,
            "total": total,
            "percentage": percentage,
        })

    context = {
        "results": results,
        "total_attempts": total_attempts,
        "unique_learners": unique_learners,
        "average_percentage": average_percentage,
        "pass_rate": pass_rate,
        "level_breakdown": level_breakdown,
    }

    return render(request, "adminpanel/results_manage.html", context)


@admin_login_required
def contacts_manage(request):
    action = request.GET.get("action")
    pk = request.GET.get("pk")
    reply_error = None
    reply_contact_id = ""
    reply_subject = "Reply from Syntax Academy"
    reply_body = ""

    if action == "delete" and pk:
        contact_message = get_object_or_404(Contact, pk=pk)
        contact_message.delete()
        return redirect("contacts_manage")

    if request.method == "POST":
        reply_contact_id = request.POST.get("contact_id", "").strip()
        reply_subject = request.POST.get("subject", "").strip() or "Reply from Syntax Academy"
        reply_body = request.POST.get("reply_message", "").strip()

        if not reply_contact_id:
            reply_error = "Choose a message to reply to."
        elif not reply_body:
            reply_error = "Reply message is required."
        else:
            contact_message = get_object_or_404(Contact, pk=reply_contact_id)

            try:
                send_mail(
                    reply_subject,
                    reply_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [contact_message.email],
                    fail_silently=False,
                )
            except Exception as exc:
                reply_error = f"Could not send email: {exc}"
            else:
                return redirect(f"{reverse('contacts_manage')}?reply=sent")

    contacts = list(Contact.objects.all().order_by("-created_at"))

    context = {
        "contacts": contacts,
        "total_contacts": len(contacts),
        "reply_error": reply_error,
        "reply_contact_id": reply_contact_id,
        "reply_subject": reply_subject,
        "reply_body": reply_body,
        "reply_success": request.GET.get("reply") == "sent",
    }

    return render(request, "adminpanel/contacts_manage.html", context)


@admin_login_required
def course_manage(request):

    action = request.GET.get('action')
    pk = request.GET.get('pk')

    # ==========================
    # DELETE
    # ==========================
    if action == "delete" and pk:
        course = get_object_or_404(Course, pk=pk)
        course.delete()
        return redirect('course_manage')

    # ==========================
    # TOGGLE ACTIVE
    # ==========================
    if action == "toggle" and pk:
        course = get_object_or_404(Course, pk=pk)
        course.is_active = not course.is_active
        course.save()
        return redirect('course_manage')

    # ==========================
    # EDIT MODE
    # ==========================
    course_instance = None
    if action == "edit" and pk:
        course_instance = get_object_or_404(Course, pk=pk)

    # ==========================
    # ADD / UPDATE (Manual)
    # ==========================
    if request.method == "POST":

        name = request.POST.get("name")
        description = request.POST.get("description")
        level = request.POST.get("level")
        duration_weeks = request.POST.get("duration_weeks")
        is_featured = True if request.POST.get("is_featured") else False
        thumbnail = request.FILES.get("thumbnail")

        if course_instance:
            # UPDATE
            course_instance.name = name
            course_instance.description = description
            course_instance.level = level
            course_instance.duration_weeks = duration_weeks
            course_instance.is_featured = is_featured
            if thumbnail:
                course_instance.thumbnail = thumbnail
            course_instance.save()
        else:
            # CREATE
            Course.objects.create(
                name=name,
                description=description,
                level=level,
                duration_weeks=duration_weeks,
                is_featured=is_featured,
                thumbnail=thumbnail
            )

        return redirect('course_manage')

    courses = Course.objects.all().order_by('-created_at')
    active_count = Course.objects.filter(is_active=True).count()
    featured_count = Course.objects.filter(is_featured=True).count()

    context = {
        "courses": courses,
        "active_count": active_count,
        "featured_count": featured_count,
        "edit_mode": course_instance,
        "course": course_instance,
    }

    return render(request, "adminpanel/course_manage.html", context)


@admin_login_required
def lesson_manage(request):

    action = request.GET.get('action')
    pk = request.GET.get('pk')

    if action == "delete" and pk:
        lesson = get_object_or_404(Lessons, pk=pk)
        lesson.delete()
        return redirect('lesson_manage')

    lesson_instance = None
    if action == "edit" and pk:
        lesson_instance = get_object_or_404(Lessons, pk=pk)

    if request.method == "POST":
        name = request.POST.get("name")
        course_id = request.POST.get("course")
        video = request.FILES.get("video")
        course = get_object_or_404(Course, pk=course_id)

        if lesson_instance:
            lesson_instance.name = name
            lesson_instance.course = course
            if video:
                lesson_instance.video = video
            lesson_instance.save()
        else:
            Lessons.objects.create(
                name=name,
                course=course,
                video=video
            )

        return redirect('lesson_manage')

    lessons = Lessons.objects.select_related('course').order_by('course__name', 'name')
    courses = Course.objects.all().order_by('name')
    total_lessons = lessons.count()
    courses_with_lessons = Course.objects.filter(lessons__isnull=False).distinct().count()

    context = {
        "lessons": lessons,
        "courses": courses,
        "total_lessons": total_lessons,
        "courses_with_lessons": courses_with_lessons,
        "edit_mode": lesson_instance,
        "lesson": lesson_instance,
    }

    return render(request, "adminpanel/lesson_manage.html", context)


@admin_login_required
def notes_manage(request):

    action = request.GET.get('action')
    pk = request.GET.get('pk')

    if action == "delete" and pk:
        note = get_object_or_404(Notes, pk=pk)
        note.delete()
        return redirect('notes_manage')

    note_instance = None
    if action == "edit" and pk:
        note_instance = get_object_or_404(Notes, pk=pk)

    if request.method == "POST":
        name = request.POST.get("name")
        course_id = request.POST.get("course")
        file = request.FILES.get("file")
        course = get_object_or_404(Course, pk=course_id)

        if note_instance:
            note_instance.name = name
            note_instance.course = course
            if file:
                note_instance.file = file
            note_instance.save()
        else:
            Notes.objects.create(
                name=name,
                course=course,
                file=file
            )

        return redirect('notes_manage')

    notes = Notes.objects.select_related('course').order_by('course__name', 'name')
    courses = Course.objects.all().order_by('name')
    total_notes = notes.count()
    courses_with_notes = Course.objects.filter(notes__isnull=False).distinct().count()

    context = {
        "notes": notes,
        "courses": courses,
        "total_notes": total_notes,
        "courses_with_notes": courses_with_notes,
        "edit_mode": note_instance,
        "note": note_instance,
    }

    return render(request, "adminpanel/note_manage.html", context)


@admin_login_required
def review_manage(request):

    action = request.GET.get('action')
    pk = request.GET.get('pk')

    if action == "delete" and pk:
        review = get_object_or_404(Review, pk=pk)
        review.delete()
        return redirect('review_manage')

    reviews = Review.objects.select_related('user', 'course').order_by('-id')
    total_reviews = reviews.count()
    average_rating = reviews.aggregate(avg=Avg('stars'))['avg'] or 0
    commented_reviews = reviews.exclude(comment__exact="").count()
    five_star_reviews = reviews.filter(stars=5).count()
    five_star_share = round((five_star_reviews / total_reviews) * 100) if total_reviews else 0

    rating_counts = {stars: reviews.filter(stars=stars).count() for stars in range(5, 0, -1)}
    rating_breakdown = []
    for stars, count in rating_counts.items():
        percentage = round((count / total_reviews) * 100) if total_reviews else 0
        rating_breakdown.append({
            "stars": stars,
            "count": count,
            "percentage": percentage,
        })

    top_courses = (
        Course.objects.filter(review__isnull=False)
        .annotate(
            review_total=Count('review'),
            average_rating=Avg('review__stars')
        )
        .order_by('-average_rating', '-review_total', 'name')[:4]
    )

    context = {
        "reviews": reviews,
        "total_reviews": total_reviews,
        "average_rating": round(average_rating, 1),
        "commented_reviews": commented_reviews,
        "five_star_reviews": five_star_reviews,
        "five_star_share": five_star_share,
        "rating_breakdown": rating_breakdown,
        "top_courses": top_courses,
    }

    return render(request, "adminpanel/review_manage.html", context)


@admin_login_required
def comments_manage(request):

    action = request.GET.get('action')
    pk = request.GET.get('pk')
    item_type = request.GET.get('type')

    if action == "delete" and pk and item_type == "comment":
        comment = get_object_or_404(Comment, pk=pk)
        comment.delete()
        return redirect('comments_manage')

    if action == "delete" and pk and item_type == "reply":
        reply = get_object_or_404(Reply, pk=pk)
        reply.delete()
        return redirect('comments_manage')

    comments = (
        Comment.objects.select_related('user', 'course')
        .prefetch_related('replies__user')
        .annotate(reply_count=Count('replies'))
        .order_by('-created_at')
    )

    total_comments = comments.count()
    total_replies = Reply.objects.count()
    replied_threads = comments.filter(reply_count__gt=0).count()
    open_threads = total_comments - replied_threads

    top_courses = (
        Course.objects.filter(comments__isnull=False)
        .annotate(
            comment_total=Count('comments', distinct=True),
            reply_total=Count('comments__replies')
        )
        .order_by('-comment_total', '-reply_total', 'name')[:4]
    )

    context = {
        "comments": comments,
        "total_comments": total_comments,
        "total_replies": total_replies,
        "replied_threads": replied_threads,
        "open_threads": open_threads,
        "top_courses": top_courses,
    }

    return render(request, "adminpanel/comments_manage.html", context)
