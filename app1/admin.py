from django.contrib import admin
from .models import *
# Register your models here.

class cor_(admin.ModelAdmin):
    list_display = ("id", "name", "level", "duration_weeks", "lessons_count", "is_featured")
    
admin.site.register(Course, cor_)

class contact_(admin.ModelAdmin):
    list_display = ("id", "name", "email", "message", "created_at")
admin.site.register(Contact, contact_)


class enr_(admin.ModelAdmin):
    list_display = ['id', 'user', 'course', 'enrolled_at'] 
admin.site.register(Enrollment, enr_)

class rev_(admin.ModelAdmin):
    list_display = ['id', 'user', 'course', 'stars', 'comment']
admin.site.register(Review, rev_)

class les_(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'video']
    
admin.site.register(Lessons, les_)

class note_(admin.ModelAdmin):
    list_display = ['id', 'name', 'course', 'file']
    
admin.site.register(Notes, note_)

class reg_(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'mobile', 'password']
    
admin.site.register(Registration, reg_)

class pay_(admin.ModelAdmin):
    list_display = ['id', 'user', 'course', 'amount', 'razorpay_payment_id', 'razorpay_order_id', 'created_at']
admin.site.register(Payment, pay_)

class comm_(admin.ModelAdmin):
    list_display = ['id', 'course', 'user', 'text', 'created_at']
    
admin.site.register(Comment,comm_)


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("comment", "user", "text", "created_at")
    search_fields = ("user__name", "text")
    list_filter = ("created_at",)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'course']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'quiz', 'correct_option']
    list_filter = ['quiz']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'quiz', 'score', 'total', 'submitted_at']
    list_filter = ['quiz', 'submitted_at']
    search_fields = ['user_email']