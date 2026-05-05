import hashlib
import hmac
import mimetypes
import os
import random
import re
from datetime import timedelta
from io import BytesIO

import requests
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage, send_mail
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.colors import HexColor, black, grey, white
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Avg, Count

from app1.serializers import QuizSerializer
from .models import (
    Comment,
    Contact,
    Course,
    Enrollment,
    Favourite,
    LessonCompletion,
    Lessons,
    Notes,
    Payment,
    Question,
    Quiz,
    Registration,
    Reply,
    Result,
    Review,
)


def get_outbound_email_sender():
    return settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or "admin@admin.com"

def demo(request):
    return render(request, 'demo.html')

def index(request):
    top_courses = (
        Course.objects
        .filter(is_active=True)
        .annotate(
            total_students=Count('enrollment', distinct=True),
            average_rating=Avg('review__stars')
        )
        .order_by('-is_featured', '-total_students', '-average_rating', '-created_at')[:4]
    )
    recent_reviews = list(
        Review.objects
        .select_related('user', 'course')
        .exclude(comment="")
        .order_by('-id')[:6]
    )

    if not recent_reviews:
        recent_reviews = list(
            Review.objects
            .select_related('user', 'course')
            .order_by('-id')[:6]
        )

    return render(request, 'index.html', {
        'top_courses': top_courses,
        'recent_reviews': recent_reviews,
        'login': 'login' in request.session,
    })


def all_courses(request):
    courses = Course.objects.all()

    return render(request, 'all_courses.html', {
        'cor': courses,
        'login': 'login' in request.session
    })


def get_course_completion_counts(user, course):
    total_lessons = Lessons.objects.filter(course=course).count()
    completed_lessons = LessonCompletion.objects.filter(
        user=user,
        lesson__course=course
    ).values("lesson_id").distinct().count()
    remaining_lessons = max(total_lessons - completed_lessons, 0)
    all_lessons_completed = total_lessons == completed_lessons

    return total_lessons, completed_lessons, remaining_lessons, all_lessons_completed


def get_certificate_status(user, course, quiz=None, all_lessons_completed=None):
    quiz = quiz or Quiz.objects.filter(course=course).order_by("id").first()

    if all_lessons_completed is None:
        _, _, _, all_lessons_completed = get_course_completion_counts(user, course)

    if not quiz:
        return quiz, None, None, False

    best_result = Result.objects.filter(
        user_email=user.email,
        quiz__course=course
    ).order_by("-score", "-submitted_at").first()

    if not best_result or not best_result.total:
        return quiz, best_result, None, False

    certificate_percentage = round((best_result.score / best_result.total) * 100, 1)
    certificate_available = all_lessons_completed and certificate_percentage >= 70

    return quiz, best_result, certificate_percentage, certificate_available

    

def search(request):
    query = request.GET.get('q')
    login = 'login' in request.session

    if query:
        results = Course.objects.filter(name__icontains=query)
    else:
        results = Course.objects.none()

    fav_ids = []
    if login:
        user_id = request.session.get('user_id')
        fav_ids = Favourite.objects.filter(user_id=user_id)\
                                    .values_list('course_id', flat=True)

    return render(request, 'search.html', {
        'results': results,
        'query': query,
        'login': login,
        'fav_ids': fav_ids,
    })



def courses(request, id):

    if 'login' not in request.session:
        return redirect('login')

    cor = get_object_or_404(Course, id=id)

    less = Lessons.objects.filter(course=cor)
    nott = Notes.objects.filter(course=cor)
    comms = Comment.objects.filter(course=cor).order_by('-created_at')
    quiz = Quiz.objects.filter(course=cor).order_by("id").first()

    # ===== USER =====
    user = Registration.objects.get(email=request.session['login'])

    # ===== ENROLLMENT =====
    is_enrolled = Enrollment.objects.filter(user=user, course=cor).exists()
    total_lessons, completed_lessons_count, remaining_lessons_count, all_lessons_completed = (0, 0, 0, False)
    completed_lesson_ids = []

    if is_enrolled:
        total_lessons, completed_lessons_count, remaining_lessons_count, all_lessons_completed = get_course_completion_counts(user, cor)
        completed_lesson_ids = list(
            LessonCompletion.objects.filter(user=user, lesson__course=cor)
            .values_list("lesson_id", flat=True)
        )

    # ===== STUDENT COUNT =====
    total_students = Enrollment.objects.filter(course=cor).count()

    # ===== REVIEW STATS =====
    review_qs = Review.objects.filter(course=cor)

    avg_rating = review_qs.aggregate(avg=Avg('stars'))['avg'] or 0
    review_count = review_qs.count()

    # Round rating to 1 decimal
    avg_rating = round(avg_rating, 1)

    # ===== USER REVIEW (For Edit Mode) =====
    user_review = Review.objects.filter(user=user, course=cor).first()
    best_quiz_result = None
    certificate_percentage = None
    certificate_available = False

    if is_enrolled:
        quiz, best_quiz_result, certificate_percentage, certificate_available = get_certificate_status(
            user,
            cor,
            quiz=quiz,
            all_lessons_completed=all_lessons_completed
        )

    return render(request, "course.html", {
        "cor": cor,
        "less": less,
        "nott": nott,
        "comms": comms,
        "quiz": quiz,
        
        "is_enrolled": is_enrolled,
        "all_lessons_completed": all_lessons_completed,
        "completed_lessons_count": completed_lessons_count,
        "remaining_lessons_count": remaining_lessons_count,
        "completed_lesson_ids": completed_lesson_ids,
        "total_lessons_count": total_lessons,
        "best_quiz_result": best_quiz_result,
        "certificate_percentage": certificate_percentage,
        "certificate_available": certificate_available,
        "total_students": total_students,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "user_review": user_review,
        
        "login": True
    })


def stream_lesson_video(request, lesson_id):

    if 'login' not in request.session:
        return HttpResponse(status=403)

    lesson = get_object_or_404(Lessons, id=lesson_id)
    user = Registration.objects.get(email=request.session['login'])

    if not Enrollment.objects.filter(user=user, course=lesson.course).exists():
        return HttpResponse(status=403)

    file_path = lesson.video.path

    if not os.path.exists(file_path):
        raise Http404("Video file not found")

    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"
    range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")

    if not range_header:
        response = FileResponse(open(file_path, "rb"), content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(file_size)
        return response

    range_match = re.match(r"bytes=(\d*)-(\d*)", range_header)

    if not range_match:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        return response

    start_str, end_str = range_match.groups()

    if start_str == "" and end_str:
        suffix_length = int(end_str)
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

    if start > end or start < 0 or end >= file_size:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        return response

    chunk_length = end - start + 1

    def file_iterator(path, offset, length, block_size=8192):
        with open(path, "rb") as video_file:
            video_file.seek(offset)
            remaining = length

            while remaining > 0:
                data = video_file.read(min(block_size, remaining))

                if not data:
                    break

                remaining -= len(data)
                yield data

    response = StreamingHttpResponse(
        file_iterator(file_path, start, chunk_length),
        status=206,
        content_type=content_type
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(chunk_length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return response


def mark_lesson_complete(request, lesson_id):

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if 'login' not in request.session:
        return JsonResponse({"error": "Login required"}, status=401)

    lesson = get_object_or_404(Lessons, id=lesson_id)
    user = Registration.objects.get(email=request.session['login'])

    if not Enrollment.objects.filter(user=user, course=lesson.course).exists():
        return JsonResponse({"error": "Enrollment required"}, status=403)

    LessonCompletion.objects.get_or_create(user=user, lesson=lesson)

    total_lessons, completed_lessons, remaining_lessons, all_lessons_completed = get_course_completion_counts(
        user,
        lesson.course
    )

    return JsonResponse({
        "status": "completed",
        "lesson_id": lesson.id,
        "completed_lessons": completed_lessons,
        "remaining_lessons": remaining_lessons,
        "total_lessons": total_lessons,
        "all_lessons_completed": all_lessons_completed
    })


def enroll_course(request, id):

    if 'login' not in request.session:
        return JsonResponse({'status': 'login_required'})

    if not razorpay_is_configured():
        return JsonResponse({
            'status': 'payment_unavailable',
            'message': 'Payment service is not configured.'
        }, status=503)

    try:
        user = Registration.objects.get(email=request.session['login'])
        course = Course.objects.get(id=id)

        enrollment = Enrollment.objects.filter(user=user, course=course)

        if enrollment.exists():
            enrollment.delete()
            return JsonResponse({'status': 'removed'})

        amount = int(course.price) * 100

        receipt = f"course{course.id}-user{user.id}-{timezone.now():%H%M%S}"
        order = create_razorpay_order(amount=amount, receipt=receipt)

        return JsonResponse({
            "status": "payment_required",
            "order_id": order["id"],
            "amount": amount,
            "key": settings.RAZORPAY_KEY_ID,
            "course_name": course.name,
            "course_id": course.id
        })

    except Exception as e:
        error_message = str(e)
        print("❌ Enroll Error:", error_message)
        return JsonResponse({
            'status': 'error',
            'message': 'Unable to create payment order. Check server logs for details.'
        }, status=502)
    
    
def submit_review(request, id):
    if 'login' not in request.session:
        return JsonResponse({'status': 'login_required'})

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        user = Registration.objects.get(email=request.session['login'])
        course = get_object_or_404(Course, id=id)

        stars = int(request.POST.get("stars"))
        comment = request.POST.get("comment")

        _, created = Review.objects.update_or_create(
            user=user,
            course=course,
            defaults={
                "stars": stars,
                "comment": comment
            }
        )

        if created:
            return JsonResponse({'status': 'created'})
        return JsonResponse({'status': 'updated'})

    except Exception as error:
        print(error)
        return JsonResponse({'status': 'error'})

def download_note(request, note_id):

    if 'login' not in request.session:
        return redirect('login')

    note = get_object_or_404(Notes, id=note_id)

    user = Registration.objects.get(email=request.session['login'])

    # Check enrollment
    if not Enrollment.objects.filter(user=user, course=note.course).exists():
        return redirect('courses', id=note.course.id)

    return FileResponse(note.file.open('rb'),
                        as_attachment=True,
                        filename=note.name + ".pdf")



def add_comm(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if 'login' not in request.session:
        return JsonResponse({"error": "Login required"}, status=401)

    course_id = request.POST.get("course_id")
    text = request.POST.get("text")

    try:
        user = Registration.objects.get(email=request.session["login"])
        course = Course.objects.get(id=course_id)
    except (Registration.DoesNotExist, Course.DoesNotExist):
        return JsonResponse({"error": "Invalid data"}, status=400)

    comment = Comment.objects.create(
        course=course,
        user=user,
        text=text
    )

    return JsonResponse({
        "user": "You",
        "text": comment.text,
        "created_at": comment.created_at.strftime("%d %b %Y, %I:%M %p"),
    })



def reply_comment(request):
    if 'login' not in request.session:
        return JsonResponse({"error": "Login required"}, status=401)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    comment_id = request.POST.get("comment_id")
    text = request.POST.get("text")

    try:
        comment = Comment.objects.get(id=comment_id)
        user = Registration.objects.get(email=request.session["login"])
    except (Comment.DoesNotExist, Registration.DoesNotExist):
        return JsonResponse({"error": "Invalid data"}, status=400)

    reply = Reply.objects.create(
        comment=comment,
        user=user,
        text=text
    )

    return JsonResponse({
        "user": user.name,
        "text": reply.text,
        "created_at": reply.created_at.strftime("%d %b %Y, %I:%M %p")
    })

def register(request):
    if request.method == 'POST':

        name = request.POST.get('name')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        level = request.POST.get('level')

        if not password or len(password) < 8 or not re.search(r'[^A-Za-z0-9]', password):
            return render(request, 'register.html', {
                'error': 'Password must be at least 8 characters and include a special character.'
            })
        
        if Registration.objects.filter(email=email).exists():
            return render(request, 'register.html', {
                'error': 'Email Already Registered!!!'
            })

        obj = Registration.objects.create(
            name=name,
            email=email,
            mobile=mobile,
            password=password,
            level=level
        )

        send_mail(
            "Welcome to Syntax Academy 🎉",
            "Your account has been successfully created.",
            get_outbound_email_sender(),
            [email],
            fail_silently=True,
        )

        request.session['login'] = obj.email
        request.session['user_name'] = obj.name
        request.session['user_id'] = obj.id

        return redirect('index')

    return render(request, 'register.html')



def login(request):
    if request.method == 'POST':
        try:
            reg = Registration.objects.get(email=request.POST['email'])
            if reg.password == request.POST['password']:
                request.session['login'] = reg.email
                request.session['user_name'] = reg.name
                request.session['user_id'] = reg.id
                return redirect('index')
            return render(request, 'login.html', {'wrong': 'Incorrect Password or Email!!!'})
        except Registration.DoesNotExist:
            return render(request, 'login.html', {'not_register': 'You have to register first!!!'})
    return render(request, 'login.html')
    
    
def logout(request):
    request.session.flush()
    return redirect('index')



@api_view(['POST'])
def upload_quiz(request):

    serializer = QuizSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response({"status": "Quiz Stored Successfully"})
    
    return Response(serializer.errors)


def quiz_page(request, course_id):

    if 'login' not in request.session:
        return redirect('login')

    course = get_object_or_404(Course, id=course_id)

    user = Registration.objects.get(email=request.session['login'])

    # Block if not enrolled
    if not Enrollment.objects.filter(user=user, course=course).exists():
        return redirect('courses', id=course.id)

    total_lessons, completed_lessons, remaining_lessons, all_lessons_completed = get_course_completion_counts(user, course)

    if not all_lessons_completed:
        messages.warning(
            request,
            f"Complete all lessons before attempting the quiz. {remaining_lessons} lesson{'s' if remaining_lessons != 1 else ''} remaining."
        )
        return redirect('courses', id=course.id)

    quizzes = Quiz.objects.filter(course=course).order_by("id")
    quiz = quizzes.first()

    if not quiz:
        return render(request, "quiz.html", {
            "no_quiz": True,
            "course": course
        })

    questions = list(Question.objects.filter(quiz__course=course))
    random.shuffle(questions)
    questions = questions[:30]

    return render(request, "quiz.html", {
        "quiz": quiz,
        "course": course,
        "quiz_title": f"{course.name} Quiz",
        "questions": questions
    })
    
    
def submit_quiz(request, course_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if 'login' not in request.session:
        return JsonResponse({"error": "Login required"}, status=401)

    course = get_object_or_404(Course, id=course_id)
    quizzes = Quiz.objects.filter(course=course).order_by("id")
    quiz = quizzes.first()

    if not quiz:
        return JsonResponse({"error": "Quiz not available"}, status=404)

    question_ids = [
        int(question_id)
        for question_id in request.POST.getlist("question_ids")
        if str(question_id).isdigit()
    ]
    questions = list(
        Question.objects.filter(quiz__course=course, id__in=question_ids)
    )
    user = Registration.objects.get(email=request.session['login'])

    if not Enrollment.objects.filter(user=user, course=course).exists():
        return JsonResponse({"error": "Enrollment required"}, status=403)

    _, _, remaining_lessons, all_lessons_completed = get_course_completion_counts(user, course)

    if not all_lessons_completed:
        return JsonResponse({
            "error": f"Complete all lessons before attempting the quiz. {remaining_lessons} lesson{'s' if remaining_lessons != 1 else ''} remaining."
        }, status=403)

    score = 0
    total = len(questions)

    for q in questions:
        selected = request.POST.get(f"question_{q.id}")

        if selected and int(selected) == q.correct_option:
            score += 1

    user_email = request.session.get('login')

    Result.objects.create(
        user_email=user_email,
        quiz=quiz,
        score=score,
        total=total
    )

    percentage = round((score / total) * 100, 1) if total else 0

    return JsonResponse({
        "score": score,
        "total": total,
        "percentage": percentage,
        "passed": percentage >= 70
    })
        

def about(request):
    if 'login' in request.session:
        return render(request, 'about.html', {'login': True})
    else:
        return render(request, 'about.html')




def profile(request):

    if 'login' not in request.session:
        return redirect('login')

    email = request.session['login']
    user = Registration.objects.get(email=email)

    enrolled_courses = Enrollment.objects.filter(user=user).select_related('course')

    # attach payment to each enrollment
    for enroll in enrolled_courses:
        enroll.payment = Payment.objects.filter(
            user=user,
            course=enroll.course
        ).first()

    # -------- UPDATE PROFILE --------
    if request.method == "POST" and request.POST.get("form_type") == "edit_profile":
        user.name = request.POST.get("name")
        user.mobile = request.POST.get("mobile")
        user.save()
        messages.success(request, "Profile updated successfully")
        return redirect('profile')

    # -------- CHANGE PASSWORD --------
    if request.method == "POST" and request.POST.get("form_type") == "change_password":
        current = request.POST.get("current_password")
        new = request.POST.get("new_password")

        if user.password == current:
            user.password = new
            user.save()
            messages.success(request, "Password changed successfully")
        else:
            messages.error(request, "Current password incorrect")

        return redirect('profile')

    # -------- QUIZ STATS --------
    results = Result.objects.filter(user_email=email)

    total_attempts = results.count()
    score_percentages = [
        (result.score / result.total) * 100
        for result in results
        if result.total
    ]
    avg_score = round(sum(score_percentages) / len(score_percentages), 2) if score_percentages else 0
    max_score = round(max(score_percentages), 2) if score_percentages else 0

    # -------- ACTIVITY --------
    comments = Comment.objects.filter(user=user).count()
    replies = Reply.objects.filter(user=user).count()

    context = {
        'user': user,
        'total_attempts': total_attempts,
        'avg_score': avg_score,
        'max_score': max_score,
        'comments': comments,
        'replies': replies,
        'enrolled_courses': enrolled_courses,
        'login': True
    }

    return render(request, 'profile.html', context)


def my_enrolls(request):

    if 'login' not in request.session:
        return redirect('login')

    email = request.session['login']
    user = Registration.objects.get(email=email)

    enrolled_courses = Enrollment.objects.filter(user=user).select_related('course').order_by('-enrolled_at')

    for enroll in enrolled_courses:
        enroll.payment = Payment.objects.filter(
            user=user,
            course=enroll.course
        ).first()

    context = {
        'user': user,
        'enrolled_courses': enrolled_courses,
        'login': True
    }

    return render(request, 'enroll_courses.html', context)


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        try:
            user = Registration.objects.get(email=email)

            otp = str(random.randint(100000, 999999))
            user.otp = otp
            user.otp_created_at = timezone.now()
            user.save()

            send_mail(
                'Syntax Academy Password Reset OTP',
                f'Your OTP is: {otp}\nValid for 60 Seconds.',
                get_outbound_email_sender(),
                [email],
                fail_silently=False,
            )

            request.session['reset_email'] = email
            return redirect('verify_otp')

        except Registration.DoesNotExist:
            return render(request, 'forgot_password.html', {'error': 'Email not registered'})

    return render(request, 'forgot_password.html')


def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        email = request.session.get('reset_email')

        if not email:
            return redirect('forgot_password')

        user = get_object_or_404(Registration, email=email)
        
        if user.otp_created_at:
            expiry_time = user.otp_created_at + timedelta(seconds=60)
            
            if timezone.now() > expiry_time:
                return render(request, 'verify_otp.html', {'error': 'OTP expired. Please request a new one.'})

        if user.otp == entered_otp:
            return redirect('reset_password')
        else:
            return render(request, 'verify_otp.html', {'error': 'Invalid OTP'})

    return render(request, 'verify_otp.html')


def reset_password(request):
    if request.method == 'POST':
        new_pass = request.POST.get('password')
        email = request.session.get('reset_email')

        if not email:
            return redirect('forgot_password')

        user = get_object_or_404(Registration, email=email)
        user.password = new_pass
        user.otp = None
        user.save()

        request.session.pop('reset_email', None)
        return redirect('login')

    return render(request, 'reset_password.html')




def contact(request):

    if 'login' not in request.session:
        return render(request, 'contact.html')

    if request.method == "POST":
        Contact.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            message=request.POST.get('message')
        )

        return redirect(reverse('contact') + '?sent=true')

    return render(request, 'contact.html', {
        'login': True,
        'success': request.GET.get('sent')
    })
    
   
def faq(request):
    if 'login' in request.session:
        return render(request,"faq.html",{'login': True})
    else:
        return render(request,"faq.html")

RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


def razorpay_is_configured():
    return bool(getattr(settings, "RAZORPAY_KEY_ID", "")) and bool(getattr(settings, "RAZORPAY_KEY_SECRET", ""))


def create_razorpay_order(amount, receipt):
    try:
        response = requests.post(
            RAZORPAY_ORDERS_URL,
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                "amount": amount,
                "currency": "INR",
                "receipt": receipt,
                "payment_capture": 1,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Invalid Razorpay credentials. Please check RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in settings.py")
        else:
            raise Exception(f"Razorpay API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        raise Exception(f"Failed to create Razorpay order: {str(e)}")


def verify_razorpay_signature(order_id, payment_id, signature):
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(generated_signature, signature)


  
@csrf_exempt
def payment_success(request):

    if 'login' not in request.session:
        return JsonResponse({'status':'login_required'})

    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method")

    if not razorpay_is_configured():
        return JsonResponse({
            'status': 'payment_unavailable',
            'message': 'Payment service is not configured.'
        }, status=503)

    try:

        user = Registration.objects.get(email=request.session['login'])
        course_id = request.POST.get("course_id")
        payment_id = request.POST.get("payment_id", "").strip()
        order_id = request.POST.get("order_id", "").strip()
        signature = request.POST.get("signature", "").strip()

        if not course_id or not payment_id or not order_id or not signature:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing payment details.'
            }, status=400)

        if not verify_razorpay_signature(order_id, payment_id, signature):
            return JsonResponse({
                'status': 'error',
                'message': 'Payment verification failed.'
            }, status=400)

        course = Course.objects.get(id=course_id)

        Enrollment.objects.get_or_create(user=user,course=course)

        payment = Payment.objects.filter(
            user=user,
            course=course,
            razorpay_payment_id=payment_id,
            razorpay_order_id=order_id,
        ).first()

        is_new_payment = payment is None
        if is_new_payment:
            payment = Payment.objects.create(
                user=user,
                course=course,
                amount=course.price,
                razorpay_payment_id=payment_id,
                razorpay_order_id=order_id,
            )

            try:
                send_payment_invoice_email(payment)
            except Exception as email_error:
                print("Invoice email error:", email_error)

        return JsonResponse({'status':'enrolled'})

    except Exception as e:
        print(e)
        return JsonResponse({'status':'error'})
    
    
def payment_receipt(request, id):

    if 'login' not in request.session:
        return redirect('login')

    user = Registration.objects.get(email=request.session['login'])

    payment = Payment.objects.get(id=id,user=user)

    return render(request,"receipt.html",{
        "payment": payment,
        "login": request.session['login'],    
    })
    
def build_receipt_pdf(payment):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=28,
        alignment=TA_RIGHT,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
    )

    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
    )

    elements = []

    # ================= HEADER =================

    header_data = [
        [
            Paragraph(
                "<b>Syntax Academy</b><br/>Premium Programming Courses<br/>support@syntaxacademy.com<br/>www.syntaxacademy.com",
                normal_style
            ),
            Paragraph("INVOICE", title_style)
        ]
    ]

    header = Table(header_data, colWidths=[300,200])

    header.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))

    elements.append(header)
    elements.append(Spacer(1,30))

    # ================= BILL INFO =================

    bill_data = [
        ["Bill To", payment.user.name],
        ["Email", payment.user.email],
        ["Invoice Number", f"INV-{payment.id}"],
        ["Date", payment.created_at.strftime("%d %B %Y")],
    ]

    bill_table = Table(bill_data, colWidths=[140,340])

    bill_table.setStyle(TableStyle([

        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("FONTNAME",(1,0),(1,-1),"Helvetica"),

        ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("LINEBELOW",(0,-1),(-1,-1),0.5,grey),

    ]))

    elements.append(bill_table)
    elements.append(Spacer(1,40))

    # ================= ITEM TABLE =================

    table_data = [
        ["Course", "Qty", "Price", "Amount"],
        [
            payment.course.name,
            "1",
            f"₹ {payment.amount}",
            f"₹ {payment.amount}"
        ]
    ]

    table = Table(table_data, colWidths=[260,60,90,110])

    table.setStyle(TableStyle([

        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,-1),"Helvetica"),

        ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("ALIGN",(2,1),(-1,-1),"RIGHT"),

        ("LINEBELOW",(0,0),(-1,0),1,black),
        ("LINEBELOW",(0,1),(-1,-1),0.25,grey),

        ("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),10),

    ]))

    elements.append(table)
    elements.append(Spacer(1,40))

    # ================= TOTAL =================

    total_table = Table([
        ["Total Amount", f" ₹ {payment.amount}"]
    ], colWidths=[350,170])

    total_table.setStyle(TableStyle([

        ("FONTNAME",(0,0),(0,0),"Helvetica-Bold"),
        ("FONTNAME",(1,0),(1,0),"Helvetica-Bold"),

        ("ALIGN",(1,0),(1,0),"RIGHT"),

        ("LINEABOVE",(0,0),(-1,0),1,black),

        ("FONTSIZE",(0,0),(-1,-1),14),
        ("TOPPADDING",(0,0),(-1,-1),12),

    ]))

    elements.append(total_table)
    elements.append(Spacer(1,50))

    # ================= FOOTER =================

    footer = Paragraph(
        "Thank you for enrolling with <b>Syntax Academy</b>. "
        "This document serves as the official payment receipt for your course purchase.",
        normal_style
    )

    elements.append(footer)

    doc.build(elements)

    return buffer.getvalue()


def send_payment_invoice_email(payment):
    pdf_bytes = build_receipt_pdf(payment)
    subject = f"Your Syntax Academy invoice for {payment.course.name}"
    body = (
        f"Hi {payment.user.name},\n\n"
        f"Thank you for purchasing {payment.course.name} on Syntax Academy.\n"
        f"Your payment of INR {payment.amount} was received successfully.\n\n"
        f"Invoice Number: INV-{payment.id}\n"
        f"Payment ID: {payment.razorpay_payment_id}\n"
        f"Purchase Date: {payment.created_at.strftime('%d %B %Y')}\n\n"
        "Your invoice PDF is attached to this email.\n\n"
        "Happy learning,\n"
        "Syntax Academy"
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=get_outbound_email_sender(),
        to=[payment.user.email],
    )
    email.attach(f"invoice_{payment.id}.pdf", pdf_bytes, "application/pdf")
    email.send(fail_silently=False)


def download_receipt(request, id):
    if 'login' not in request.session:
        return redirect('login')

    user = Registration.objects.get(email=request.session['login'])
    payment = get_object_or_404(Payment, id=id, user=user)
    pdf_bytes = build_receipt_pdf(payment)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{payment.id}.pdf"'

    return response


def download_certificate(request, course_id):

    if 'login' not in request.session:
        return redirect('login')

    course = get_object_or_404(Course, id=course_id)
    user = Registration.objects.get(email=request.session['login'])

    if not Enrollment.objects.filter(user=user, course=course).exists():
        return redirect('courses', id=course.id)

    quiz, best_result, certificate_percentage, certificate_available = get_certificate_status(user, course)

    if not certificate_available:
        messages.warning(
            request,
            "Complete all lessons and score at least 70% in the quiz to download your certificate."
        )
        return redirect('courses', id=course.id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"certificate_{course.id}.pdf\"'

    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(response, pagesize=(page_width, page_height))

    navy = HexColor("#081225")
    panel = HexColor("#0f1b34")
    panel_soft = HexColor("#152544")
    royal = HexColor("#2563eb")
    sky = HexColor("#38bdf8")
    aqua = HexColor("#67e8f9")
    ink = HexColor("#111827")
    muted = HexColor("#667085")
    border = HexColor("#d5deec")
    soft_bg = HexColor("#f6f9ff")

    issued_on = best_result.submitted_at.strftime("%d %B %Y") if best_result else timezone.now().strftime("%d %B %Y")
    duration_text = f"{course.duration_weeks} week{'s' if course.duration_weeks != 1 else ''}"
    level_text = course.get_level_display()
    summary_text = re.sub(r"\s+", " ", (course.description or "").strip())
    if len(summary_text) > 260:
        summary_text = summary_text[:257].rstrip() + "..."

    script_font = "Helvetica-Bold"
    serif_font = "Helvetica"
    serif_bold_font = "Helvetica-Bold"

    windows_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    font_candidates = [
        ("CertificateSerif", os.path.join(windows_fonts, "georgia.ttf")),
        ("CertificateSerifBold", os.path.join(windows_fonts, "georgiab.ttf")),
        ("CertificateSerifItalic", os.path.join(windows_fonts, "georgiai.ttf")),
    ]

    for font_name, font_path in font_candidates:
        if os.path.exists(font_path) and font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))

    if "CertificateSerif" in pdfmetrics.getRegisteredFontNames():
        serif_font = "CertificateSerif"
    if "CertificateSerifBold" in pdfmetrics.getRegisteredFontNames():
        serif_bold_font = "CertificateSerifBold"
    if "CertificateSerifItalic" in pdfmetrics.getRegisteredFontNames():
        script_font = "CertificateSerifItalic"

    def blend_hex(start_hex, end_hex, ratio):
        start_hex = start_hex.lstrip("#")
        end_hex = end_hex.lstrip("#")
        sr, sg, sb = int(start_hex[0:2], 16), int(start_hex[2:4], 16), int(start_hex[4:6], 16)
        er, eg, eb = int(end_hex[0:2], 16), int(end_hex[2:4], 16), int(end_hex[4:6], 16)
        rr = round(sr + (er - sr) * ratio)
        rg = round(sg + (eg - sg) * ratio)
        rb = round(sb + (eb - sb) * ratio)
        return HexColor(f"#{rr:02x}{rg:02x}{rb:02x}")

    pdf.setFillColor(white)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    pdf.setStrokeColor(border)
    pdf.setLineWidth(1.4)
    pdf.rect(18, 18, page_width - 36, page_height - 36, fill=0, stroke=1)

    header_height = 190
    gradient_steps = 80
    for step in range(gradient_steps):
        ratio = step / max(gradient_steps - 1, 1)
        pdf.setFillColor(blend_hex("#081225", "#2563eb", ratio))
        strip_width = page_width / gradient_steps
        pdf.rect(step * strip_width, page_height - header_height, strip_width + 2, header_height, fill=1, stroke=0)

    diagonal = pdf.beginPath()
    diagonal.moveTo(page_width * 0.52, page_height)
    diagonal.lineTo(page_width, page_height)
    diagonal.lineTo(page_width, page_height - header_height)
    diagonal.close()
    pdf.setFillColor(white)
    pdf.drawPath(diagonal, fill=1, stroke=0)

    shadow = pdf.beginPath()
    shadow.moveTo(0, page_height - header_height + 2)
    shadow.lineTo(page_width * 0.53, page_height - 2)
    shadow.lineTo(page_width * 0.54, page_height - 16)
    shadow.lineTo(0, page_height - header_height - 12)
    shadow.close()
    pdf.setFillColor(HexColor("#0f172a"))
    pdf.drawPath(shadow, fill=1, stroke=0)

    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(38, page_height - 108, "CERTIFICATE OF")
    pdf.setFont("Helvetica-Bold", 40)
    pdf.drawString(38, page_height - 150, "COMPLETION")

    brand_x = page_width - 248
    brand_y = page_height - 126
    brand_width = 194
    brand_height = 86
    pdf.setFillColor(HexColor("#f8fbff"))
    pdf.roundRect(brand_x, brand_y, brand_width, brand_height, 18, fill=1, stroke=0)
    pdf.setStrokeColor(HexColor("#294169"))
    pdf.setLineWidth(1.2)
    pdf.roundRect(brand_x, brand_y, brand_width, brand_height, 18, fill=0, stroke=1)

    logo_holder_x = brand_x + 20
    logo_holder_y = brand_y + 20
    pdf.setFillColor(navy)
    pdf.circle(logo_holder_x + 22, logo_holder_y + 22, 24, fill=1, stroke=0)
    pdf.setFillColor(royal)
    pdf.circle(logo_holder_x + 22, logo_holder_y + 22, 20, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.circle(logo_holder_x + 22, logo_holder_y + 22, 16, fill=1, stroke=0)

    logo_path = os.path.join(settings.BASE_DIR, "app1", "static", "img", "logo.png")
    if os.path.exists(logo_path):
        pdf.drawImage(ImageReader(logo_path), logo_holder_x + 8, logo_holder_y + 8, width=28, height=28, mask="auto")

    pdf.setFillColor(navy)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(brand_x + 72, brand_y + 48, "Syntax")
    pdf.setFillColor(royal)
    pdf.drawString(brand_x + 72, brand_y + 28, "Academy")
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(brand_x + 72, brand_y + 14, "LEARNING CERTIFICATE")

    seal_center_x = page_width - 110
    seal_center_y = page_height - 210
    pdf.setFillColor(panel)
    pdf.circle(seal_center_x, seal_center_y, 36, fill=1, stroke=0)
    pdf.setFillColor(royal)
    pdf.circle(seal_center_x, seal_center_y, 31, fill=1, stroke=0)
    pdf.setFillColor(aqua)
    pdf.circle(seal_center_x, seal_center_y, 25, fill=0, stroke=1)
    pdf.setLineWidth(2)
    pdf.setStrokeColor(aqua)
    pdf.circle(seal_center_x, seal_center_y, 25, fill=0, stroke=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(seal_center_x, seal_center_y + 6, "COURSE")
    pdf.drawCentredString(seal_center_x, seal_center_y - 8, "COMPLETE")

    ribbon = pdf.beginPath()
    ribbon.moveTo(seal_center_x - 19, seal_center_y - 28)
    ribbon.lineTo(seal_center_x - 10, seal_center_y - 76)
    ribbon.lineTo(seal_center_x + 1, seal_center_y - 62)
    ribbon.lineTo(seal_center_x + 11, seal_center_y - 76)
    ribbon.lineTo(seal_center_x + 20, seal_center_y - 28)
    ribbon.close()
    pdf.setFillColor(navy)
    pdf.drawPath(ribbon, fill=1, stroke=0)

    center_x = page_width / 2

    pdf.setFillColor(muted)
    pdf.setFont(serif_font, 21)
    pdf.drawCentredString(center_x, page_height - 250, "This is to certify that")

    display_name = " ".join((user.name or "").split()) or "Student"
    display_name = display_name.title()

    name_font_size = 30
    pdf.setFillColor(ink)
    pdf.setFont(script_font, name_font_size)
    while pdf.stringWidth(display_name, script_font, name_font_size) > 280 and name_font_size > 22:
        name_font_size -= 1
        pdf.setFont(script_font, name_font_size)
    pdf.drawCentredString(center_x, page_height - 310, display_name)

    pdf.setStrokeColor(HexColor("#c7d2e5"))
    pdf.setLineWidth(1.1)
    pdf.line(center_x - 170, page_height - 338, center_x + 170, page_height - 338)

    pdf.setFillColor(panel)
    pdf.setFont(serif_font, 14)
    pdf.drawCentredString(center_x, page_height - 368, "has successfully completed the course")

    pdf.setFillColor(royal)
    course_title = course.name.upper()
    course_font_size = 18
    pdf.setFont(serif_bold_font, course_font_size)
    while pdf.stringWidth(course_title, serif_bold_font, course_font_size) > 360 and course_font_size > 14:
        course_font_size -= 1
        pdf.setFont(serif_bold_font, course_font_size)
    pdf.drawCentredString(center_x, page_height - 397, course_title)

    chip_y = page_height - 462
    chip_width = 124
    chip_height = 46
    chip_gap = 14
    chip_start_x = center_x - (chip_width * 1.5) - chip_gap

    chip_values = [
        ("Duration", duration_text),
        ("Score", f"{certificate_percentage}%"),
        ("Level", level_text),
    ]

    for index, (label, value) in enumerate(chip_values):
        chip_x = chip_start_x + index * (chip_width + chip_gap)
        pdf.setFillColor(panel_soft)
        pdf.roundRect(chip_x, chip_y, chip_width, chip_height, 14, fill=1, stroke=0)
        pdf.setFillColor(aqua if index == 0 else sky if index == 1 else white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(chip_x + (chip_width / 2), chip_y + 30, label.upper())
        pdf.setFillColor(white)
        pdf.setFont("Helvetica-Bold", 11.5)
        pdf.drawCentredString(chip_x + (chip_width / 2), chip_y + 14, value)

    pdf.setFillColor(panel)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(center_x, page_height - 490, "WHAT YOU LEARNED")

    styles = getSampleStyleSheet()
    summary_style = ParagraphStyle(
        "CertificateSummary",
        parent=styles["Normal"],
        fontName=serif_font,
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=ink,
    )

    summary = Paragraph(
        summary_text or "Core concepts, guided lessons, and practical knowledge successfully completed.",
        summary_style
    )
    summary_width = page_width - 192
    wrapped_width, wrapped_height = summary.wrap(summary_width - 120, 40)
    summary.drawOn(
        pdf,
        (page_width - wrapped_width) / 2,
        page_height - 505 - wrapped_height
    )

    pdf.setStrokeColor(ink)
    pdf.setLineWidth(1)
    pdf.line(124, 60, 284, 60)
    pdf.line(page_width - 284, 60, page_width - 124, 60)

    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(204, 42, issued_on)
    pdf.drawCentredString(page_width - 204, 42, "Syntax Academy")

    pdf.showPage()
    pdf.save()

    return response
