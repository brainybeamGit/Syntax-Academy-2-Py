from django.urls import path
from .views import *
from . import views

urlpatterns = [
    path('', index, name='index'),
    path('all-courses/', all_courses, name='all_courses'),
    path('lesson-video/<int:lesson_id>/', views.stream_lesson_video, name='stream_lesson_video'),
    path('lesson-complete/<int:lesson_id>/', views.mark_lesson_complete, name='mark_lesson_complete'),
    path('certificate/<int:course_id>/', views.download_certificate, name='download_certificate'),
    path('enroll/<int:id>/', views.enroll_course, name='enroll_course'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('receipt/<int:id>/',views.payment_receipt,name="payment_receipt"),
    path('receipt/download/<int:id>/',views.download_receipt,name="download_receipt"),
    path('demo/', demo, name='demo'),
    path('contact/', contact, name='contact'),
    path('search/', views.search, name='search'),
    path("courses/<int:id>/", courses, name="courses"),
    path('review/<int:id>/', views.submit_review, name='submit_review'),
    path('download/note/<int:note_id>/', views.download_note, name='download_note'),
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('add_comm/', views.add_comm, name='add_comm'),
    path("reply_comment/", views.reply_comment, name='reply_comment'),
    path('api/upload-quiz/', views.upload_quiz),
    path('quiz_page/<int:course_id>/', views.quiz_page, name='quiz_page'),
    path('submit_quiz/<int:course_id>/', views.submit_quiz, name='submit_quiz'),
    path('about/', about, name='about'),
    path('profile/', profile, name='profile'),
    path('my-enrolls/', my_enrolls, name='my_enrolls'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('faq/', faq, name='faq'),

]
