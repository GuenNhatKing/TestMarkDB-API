from rest_framework import serializers
from .models import *
from .tasks import upload_image, get_image_url

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'isVerificated')
    
class ExamSerializer(serializers.ModelSerializer):
    exampaper_count = serializers.SerializerMethodField()
    class Meta: 
        model = Exam
        fields = '__all__'
        extra_kwargs = {
            'user': {'read_only': True}, 
            'exampaper_count': {'read_only': True}
        }
    
    def get_exampaper_count(self, obj):
        return ExamPaper.objects.filter(exam=obj).count()

class ExamPaperSerializer(serializers.ModelSerializer):
    class Meta: 
        model = ExamPaper
        fields = '__all__'
        extra_kwargs = {
            'exam': {'read_only': True} 
        }

class ExamAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAnswer
        fields = ('id', 'question_number', 'answer_number')

class ExamPaperBatchAnswerSerializer(serializers.Serializer):
    answers = serializers.JSONField()
    class Meta:
        model = ExamAnswer
        fields = '__all__'
        extra_kwargs = {
            'exam_paper': {'read_only': True} 
        }
    
class ExamineeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Examinee
        fields = '__all__'
        extra_kwargs = {
            'user': {'read_only': True} 
        }

class OTPRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTPRequest
        fields = ('request', 'created_at', 'expired_at')

class RequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionRequest
        fields = ('user', 'token', 'action', 'available', 'expired_at')

ALLOWED_ACTIONS = ['email_verify', 'password_reset']
class SendOTPForVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    action = serializers.ChoiceField(choices=ALLOWED_ACTIONS, required=True)

class OTPVerifySerializer(serializers.Serializer):
    token = serializers.CharField(max_length=24)
    code = serializers.CharField(max_length=4)

class EmailVerifySerializer(serializers.Serializer):
    token = serializers.CharField(max_length=24)

class CameraStreamSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

class ImageUrlSerializer(serializers.Serializer):
    image_name = serializers.CharField(required=True)

class ExamineeRecordSerializer(serializers.ModelSerializer):
    img_before_process_input = serializers.ImageField(write_only=True, required=False)
    img_before_process = serializers.CharField(read_only=True) 
    class Meta:
        model = ExamineeRecord
        fields = '__all__'
        extra_kwargs = {
            'exam': {'read_only': True}, 
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        raw = instance.img_before_process

        data["img_before_process"] = (
            get_image_url(raw) if raw else None
        )
        return data
    
    def create(self, validated_data):
        img_before_file = validated_data.pop("img_before_process_input", None)
        
        if img_before_file:
            validated_data["img_before_process"] = upload_image(file=img_before_file) 
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        img_before_file = validated_data.pop("img_before_process_input", None)

        if img_before_file:
            instance.img_before_process = upload_image(file=img_before_file)
        return super().update(instance, validated_data)
    
class ExamineeRecordDetailSerializer(serializers.ModelSerializer):
    examinee_id = serializers.IntegerField(source='id', read_only=True)
    examinee_name = serializers.CharField(source='name', read_only=True)
    records = serializers.SerializerMethodField()

    class Meta:
        model = Examinee
        fields = ('examinee_id', 'examinee_name', 'records')

    def get_records(self, obj):
        record_qs = (
            ExamineeRecord.objects
            .filter(examinee=obj)
            .select_related('exam')
        )

        out = []

        for rec in record_qs:
            exam = rec.exam 

            ep_qs = (
                ExamineePaper.objects
                .filter(examinee=obj, exam_paper__exam=exam)
                .select_related('exam_paper')
            )

            exam_paper = ep_qs.first().exam_paper if ep_qs.exists() else None
            correct_answers = ep_qs.filter(mark_result=True).count()

            exam_dict = {
                "exam_id": exam.id,
                "exam_name": exam.name,
                "subject": exam.subject,
                "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
                "exam_paper": {
                    "paper_id": exam_paper.id if exam_paper else None,
                    "paper_code": exam_paper.exam_paper_code if exam_paper else None,
                    "number_of_questions": exam_paper.number_of_questions if exam_paper else None,
                },
                "result": {
                    "correct_answers": correct_answers,
                    "score": rec.score,
                    "img_before_process": get_image_url(rec.img_before_process) if rec.img_before_process else None,
                }
            }

            out.append(exam_dict)

        return out

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=24)
    new_password = serializers.CharField(required=True)

class ImageProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamineeRecord
        fields = '__all__'
        extra_kwargs = {
            'examinee_code': {'read_only': True},
        }

class ImageProcessSaveSerializer(serializers.Serializer):
    result = serializers.JSONField()
    class Meta:
        model = ExamineeRecord
        fields = '__all__'
        extra_kwargs = {
            'examinee_code': {'read_only': True},
        }

class ExamineeResultSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField()
    class Meta:
        model = ExamineeRecord
        fields = ('id', 'exam', 'examinee', 'result')
        extra_kwargs = {
            'exam': {'read_only': True},
            'examinee': {'read_only': True},
        }
    
    def get_result(self, obj):
        exam_results = ExamineePaper.objects.filter(examinee=obj.examinee, exam_paper__exam=obj.exam)
        results_list = []
        for er in exam_results:
            results_list.append({
                'question_number': er.question_number,
                'answer_number': er.answer_number,
                'mark_result': er.mark_result
            })
        
        result = {
            'exam_paper_code': obj.exam.exampaper_set.filter(exam=obj.exam).first().exam_paper_code if obj.exam.exampaper_set.filter(exam=obj.exam).exists() else None,
            'total_questions': exam_results.count(),
            'correct_answers': exam_results.filter(mark_result=True).count(),
            'score': obj.score,
            'details': results_list
        }
        return result