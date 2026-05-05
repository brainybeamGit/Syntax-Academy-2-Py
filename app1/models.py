from django.db import models


# Create your models here.

class Course(models.Model):

    LEVEL_CHOICES = [
        ('beginner','Beginner'),
        ('intermediate','Intermediate'),
        ('advanced','Advanced'),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to="courses/", null=True, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    duration_weeks = models.IntegerField(default=4)
    price = models.IntegerField(default=999)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def lessons_count(self):
        return self.lessons_set.count()

    def students_count(self):
        return self.enrollment_set.count()

    def avg_rating(self):
        reviews = self.review_set.all()
        if reviews.exists():
            return round(sum(r.stars for r in reviews)/reviews.count(),1)
        return 0

    def __str__(self):
        return self.name
    
    
class Registration(models.Model):

    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('pro', 'Pro Developer'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile = models.IntegerField()
    password = models.CharField(max_length=10)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    level = models.CharField(max_length=20,choices=LEVEL_CHOICES,default='beginner')

    def __str__(self):
        return self.name



class Enrollment(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user','course')

    def __str__(self):
        return f"{self.user.name} enrolled in {self.course.name}"


class Payment(models.Model):

    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    amount = models.IntegerField()

    razorpay_payment_id = models.CharField(max_length=200)
    razorpay_order_id = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name} - {self.course.name}"
    

class Review(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    stars = models.IntegerField()  # 1 to 5
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ('user','course')

    def __str__(self):
        return f"{self.course.name} - {self.stars}⭐"
    



class Favourite(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user','course')

    def __str__(self):
        return f"{self.user.name} â¤ï¸ {self.course.name}"


class Quiz(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question_text = models.TextField()

    option1 = models.CharField(max_length=200)
    option2 = models.CharField(max_length=200)
    option3 = models.CharField(max_length=200)
    option4 = models.CharField(max_length=200)

    correct_option = models.IntegerField()  # 1,2,3,4

    def __str__(self):
        return self.question_text


class Result(models.Model):
    user_email = models.CharField(max_length=200)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)

    score = models.IntegerField()
    total = models.IntegerField()

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_email} - {self.quiz.title} - {self.score}/{self.total}"


class Comment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name} - {self.course.name}"
    
    
class Reply(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply by {self.user.name}"
  
class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Lessons(models.Model):
    name = models.CharField(max_length=100)
    video = models.FileField(upload_to='videos/')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name


class LessonCompletion(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lessons, on_delete=models.CASCADE, related_name="completions")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'lesson')

    def __str__(self):
        return f"{self.user.name} completed {self.lesson.name}"
    
class Notes(models.Model):
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='notes/')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name
    

