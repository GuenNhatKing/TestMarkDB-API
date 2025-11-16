from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
# Create your models here.

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    isVerificated = models.BooleanField(default=False) # Email verificate

    def __str__(self):
        return f"{self.username} ({self.email})"
    
class Examinee(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=127)
    student_ID = models.CharField(max_length=10, unique=True, null=True)
    date_of_birth = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.date_of_birth})"

class Exam(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=127)
    subject = models.CharField(max_length=127, null=True)
    description = models.TextField(null = True)
    exam_date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.exam_date})"
    
class ExamPaper(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    exam_paper_code = models.CharField(max_length=6)
    number_of_questions = models.IntegerField()
    
    def __str__(self):
        return f"{self.exam.name} - Paper {self.exam_paper_code}"

class ExamineeRecord(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    examinee = models.ForeignKey(Examinee, on_delete=models.CASCADE)
    examinee_code = models.CharField(max_length=6)
    score = models.FloatField(null=True)
    img_before_process = models.CharField(max_length=255, null=True)
    
    def __str__(self):
        return f"{self.examinee.name} - {self.exam.name}: {self.score}"

class ExamAnswer(models.Model):
    exam_paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE)
    question_number = models.IntegerField()
    answer_number = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    
    def __str__(self):
        return f"{self.exam_paper} Q{self.question_number}: A{self.answer_number}"

class ExamineePaper(models.Model):
    exam_paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE)
    examinee = models.ForeignKey(Examinee, on_delete=models.CASCADE)
    question_number = models.IntegerField()
    answer_number = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(3)])
    mark_result = models.BooleanField()

    def __str__(self):
        mark = "Correct" if self.mark_result else "Wrong"
        return f"{self.examinee.name} - {self.exam_paper} Q{self.question_number}: A{self.answer_number} ({mark})"
    
class ActionRequest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=24, primary_key=True)
    action = models.CharField(max_length=64)
    available = models.BooleanField()
    expired_at = models.DateTimeField()

    def __str__(self):
        return f'{self.user.email} {self.action} ({self.token})'

class OTPRequest(models.Model):
    code = models.CharField(max_length=4)
    request = models.ForeignKey(ActionRequest, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    expired_at = models.DateTimeField()

    def __str__(self):
        return f'{self.request.user.email} ({self.code})'
# TODO: Thêm count để đếm số lượng exampaper trong exam
# TODO: Loại bỏ trường Duration trong Exam
    