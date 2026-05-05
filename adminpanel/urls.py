from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('', views.dashboard_home, name='dashboard_home'),
    path('students/', views.students_manage, name='students_manage'),
    path('enrollments/', views.enrollments_manage, name='enrollments_manage'),
    path('quizzes/', views.quiz_manage, name='quiz_manage'),
    path('quizzes/<int:quiz_id>/questions/', views.quiz_questions_manage, name='quiz_questions_manage'),
    path('results/', views.results_manage, name='results_manage'),
    path('contacts/', views.contacts_manage, name='contacts_manage'),
    path('courses/', views.course_manage, name='course_manage'),
    path('lessons/', views.lesson_manage, name='lesson_manage'),
    path('notes/', views.notes_manage, name='notes_manage'),
    path('reviews/', views.review_manage, name='review_manage'),
    path('comments/', views.comments_manage, name='comments_manage'),
]
