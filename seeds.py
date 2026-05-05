import os
import django
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "syn.settings")
django.setup()

from app1.models import (
    Registration,
    Course,
    Enrollment,
    Payment,
    Review,
    Favourite,
    Quiz,
    Question,
    Result,
    Comment,
    Reply,
    Contact,
    Lessons,
    LessonCompletion,
    Notes,
)


@transaction.atomic
def run():
    print("Seeding database...")

    # Admin seed (exact credentials required)
    admin, created = Registration.objects.update_or_create(
        email="admin@gmail.com",
        defaults={
            "name": "admin",
            "mobile": 9999999999,
            "password": "admin",
            "level": "pro",
        },
    )
    if created:
        print("Created admin user: admin / admin")
    else:
        print("Admin user ensured")

    # Create sample courses
    course_specs = [
        {"name": "Python Foundations", "description": "Intro to Python", "price": 999, "level": "beginner"},
        {"name": "Django Starter", "description": "Build Django apps", "price": 1499, "level": "intermediate"},
        {"name": "Web Fundamentals", "description": "HTML/CSS/JS basics", "price": 799, "level": "beginner"},
        {"name": "APIs with DRF", "description": "REST APIs using Django REST Framework", "price": 1299, "level": "intermediate"},
        {"name": "Git & Workflow", "description": "Version control and collaboration", "price": 499, "level": "beginner"},
    ]
    courses = {}
    for spec in course_specs:
        c, _ = Course.objects.update_or_create(name=spec["name"], defaults={**spec, "is_active": True})
        courses[c.name] = c

    # Create demo students (5 users)
    students_data = [
        {"name": "Ava Patel", "email": "ava@example.com", "mobile": 9876543210, "password": "demo123!", "level": "beginner"},
        {"name": "Noah Sharma", "email": "noah@example.com", "mobile": 9876501234, "password": "demo123!", "level": "intermediate"},
        {"name": "Mia Verma", "email": "mia@example.com", "mobile": 9876505678, "password": "demo123!", "level": "advanced"},
        {"name": "Liam Roy", "email": "liam@example.com", "mobile": 9876512345, "password": "demo123!", "level": "beginner"},
        {"name": "Sophia Khan", "email": "sophia@example.com", "mobile": 9876523456, "password": "demo123!", "level": "intermediate"},
    ]
    students = {}
    for s in students_data:
        obj, _ = Registration.objects.update_or_create(email=s["email"], defaults=s)
        students[obj.email] = obj

    # Enroll some students and create payments
    Enrollment.objects.get_or_create(user=students["ava@example.com"], course=courses["Python Foundations"])
    Payment.objects.get_or_create(user=students["ava@example.com"], course=courses["Python Foundations"], defaults={"amount": courses["Python Foundations"].price, "razorpay_payment_id": "pay_python_ava", "razorpay_order_id": "order_python_ava"})

    Enrollment.objects.get_or_create(user=students["noah@example.com"], course=courses["Django Starter"])
    Payment.objects.get_or_create(user=students["noah@example.com"], course=courses["Django Starter"], defaults={"amount": courses["Django Starter"].price, "razorpay_payment_id": "pay_django_noah", "razorpay_order_id": "order_django_noah"})

    # Reviews and favourites
    Review.objects.update_or_create(user=students["ava@example.com"], course=courses["Python Foundations"], defaults={"stars": 5, "comment": "Great pacing and practical exercises."})
    Favourite.objects.get_or_create(user=students["noah@example.com"], course=courses["Django Starter"])

    # Quizzes and questions
    quiz, _ = Quiz.objects.update_or_create(course=courses["Python Foundations"], title="Python Foundations Quiz")
    questions = [
        {"question_text": "Which keyword defines a function in Python?", "option1": "func", "option2": "def", "option3": "function", "option4": "fn", "correct_option": 2},
        {"question_text": "Which command installs packages?", "option1": "pip install pkg", "option2": "python install pkg", "option3": "install pkg", "option4": "pkg add", "correct_option": 1},
    ]
    for q in questions:
        Question.objects.update_or_create(quiz=quiz, question_text=q["question_text"], defaults=q)

    # Results
    Result.objects.update_or_create(user_email=students["ava@example.com"].email, quiz=quiz, defaults={"score": 4, "total": 4})

    # Comments and replies
    comment, _ = Comment.objects.update_or_create(course=courses["Python Foundations"], user=students["ava@example.com"], defaults={"text": "Fantastic intro course!"})
    Reply.objects.get_or_create(comment=comment, user=students["noah@example.com"], defaults={"text": "I agree, very clear explanations."})

    # Contact message
    Contact.objects.get_or_create(email="hello@example.com", defaults={"name": "Site Visitor", "message": "I love the course selection."})

    # Lessons and notes
    lesson, _ = Lessons.objects.update_or_create(name="Intro to Python", course=courses["Python Foundations"], defaults={"video": "videos/intro.mp4"})
    Notes.objects.update_or_create(name="Python Basics Notes", course=courses["Python Foundations"], defaults={"file": "notes/python_basics.pdf"})
    LessonCompletion.objects.get_or_create(user=students["ava@example.com"], lesson=lesson)

    print("Seeding complete.")


if __name__ == "__main__":
    run()
