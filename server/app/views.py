from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .permissions import IsVerificated
from .models import *
from .serializers import *
from .tasks import *
from app import randomX
from datetime import datetime, timedelta
import time
from django.http import HttpResponse, Http404
from django.db import transaction

class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    queryset = CustomUser.objects.all()
    serializer_class = UserRegisterSerializer

class ExamViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsVerificated]
    serializer_class = ExamSerializer
    def get_queryset(self):
        queryset = Exam.objects.filter(user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ExamPaperViewSet(viewsets.ModelViewSet):
    serializer_class = ExamPaperSerializer
    def get_queryset(self):
        exam_id = self.kwargs.get('exam_pk')
        return ExamPaper.objects.filter(exam_id=exam_id)

    def perform_create(self, serializer):
        exam_id = self.kwargs.get('exam_pk')
        exam = Exam.objects.filter(pk=exam_id).first()
        if not exam:
            raise Http404("Exam not found")
        serializer.save(exam_id=exam_id)

class ExamAnswerViewSet(viewsets.ModelViewSet):
    serializer_class = ExamAnswerSerializer
    def get_queryset(self):
        exam_paper_id = self.kwargs.get('exam_paper_pk')
        return ExamAnswer.objects.filter(exam_paper_id=exam_paper_id)

    def perform_create(self, serializer):
        exam_paper_id = self.kwargs.get('exam_paper_pk')
        exam_paper = ExamPaper.objects.filter(pk=exam_paper_id).first()
        if not exam_paper:
            raise Http404("ExamPaper not found")
        serializer.save(exam_paper_id=exam_paper_id)
    
class ExamineeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsVerificated]
    serializer_class = ExamineeSerializer
    def get_queryset(self):
        return Examinee.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ExamineeRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ExamineeRecordSerializer
    def get_queryset(self):
        exam_id = self.kwargs.get('exam_pk')
        return ExamineeRecord.objects.filter(exam_id=exam_id)

    def perform_create(self, serializer):
        exam_id = self.kwargs.get('exam_pk')
        exam = Exam.objects.filter(pk=exam_id).first()
        if not exam:
            raise Http404("Exam not found")
        serializer.save(exam_id=exam_id)

class ExamineeRecordDetailView(APIView):
    serializer_class = ExamineeRecordDetailSerializer
    def get(self, request, examinee_id):
        examinee = Examinee.objects.filter(pk=examinee_id).first()
        if not examinee:
            return Response({"detail": "Examinee not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ExamineeRecordDetailSerializer(examinee)
        return Response(serializer.data, status=status.HTTP_200_OK)

# POST ExamPaper's Answer using JSON
class ExamPaperBatchAnswerView(APIView):
    serializer_class = ExamPaperBatchAnswerSerializer
    def post(self, request, exam_paper_pk):
        exam_paper = ExamPaper.objects.filter(pk=exam_paper_pk).first()
        if not exam_paper:
            return Response({"detail": "ExamPaper not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ExamPaperBatchAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data['answers']

        with transaction.atomic():
            for ans in answers:
                question_number = ans.get('question_number')
                answer_number = ans.get('answer_number')
                exam_answer = ExamAnswer.objects.filter(exam_paper=exam_paper, question_number=question_number).first()
                if exam_answer:
                    exam_answer.answer_number = answer_number
                    exam_answer.save()
                    continue
                exam_answer = ExamAnswer(exam_paper=exam_paper, question_number=question_number, answer_number=answer_number)
                exam_answer.save()

        return Response({"detail": "Answers saved successfully"}, status=status.HTTP_201_CREATED)

class ExamineeResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExamineeResultSerializer
    def get_queryset(self):
        examineeRecord = self.kwargs.get('examinee_record_pk')
        return ExamineeRecord.objects.filter(pk=examineeRecord)

ACTIONS = ['email_verify', 'password_reset']

class SendOTPForVerify(APIView):
    def post(self, request):
        action = request.data.get('action', '')
        if action not in ACTIONS:
            return Response({"detail": "Hành động không hợp lệ", "allowed_actions": ACTIONS}, status=status.HTTP_400_BAD_REQUEST)

        action_request = ActionRequest.objects.filter(
            user = request.user,
            available = False,
            expired_at__gt = datetime.now(),
            action=action
        ).first()

        if action_request is None:
            token = ''.join(map(str, [randomX.base62[x] for x in randomX.randomX(24, 0, 62)]))
            action_request = ActionRequest(user=request.user, token=token, action=action, expired_at=datetime.now() + timedelta(minutes=5), available=False)
            action_request.save()

        otp_code = randomX.randomOTP()
        otp_request = OTPRequest(code=otp_code, request=action_request, created_at=datetime.now(), expired_at=datetime.now() + timedelta(minutes=5))
        otp_request.save()

        serializer = OTPRequestSerializer(otp_request)

        send_otp.delay(action_request.user.email, otp_code)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class VerifyOTP(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        token = serializer.validated_data['token']

        action_request = ActionRequest.objects.filter(token=token, available=False, expired_at__gt = datetime.now()).first()
        if action_request is None:
            return Response({"detail": "Token không hợp lệ"}, status=status.HTTP_400_BAD_REQUEST)
        
        otp_request = OTPRequest.objects.filter(
            request=action_request,
            code = code,
            expired_at__gt = datetime.now()
        ).first()

        if otp_request is None:
            return Response({"detail": "OTP không hợp lệ hoặc đã hết hạn"}, status=status.HTTP_400_BAD_REQUEST)

        action_request.available = True
        action_request.save()
        serializer = RequestSerializer(action_request)

        otp_request.delete()

        return Response(serializer.data, status=status.HTTP_200_OK)

class VerifyEmail(APIView):
    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']

        action_request = ActionRequest.objects.filter(token=token, available=True, expired_at__gt = datetime.now()).first()
        if action_request is None:
            return Response({"detail": "Token không hợp lệ"}, status=status.HTTP_400_BAD_REQUEST)
        
        user = CustomUser.objects.filter(username=action_request.user.username).first()
        user.isVerificated = True
        user.save()
        action_request.delete()
        return Response({"detail": "Xác thực email thành công"}, status=status.HTTP_200_OK)

class ChangePassword(APIView):
    permission_classes = [IsAuthenticated, IsVerificated]
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        user = request.user
        if not user.check_password(old_password):
            return Response({"detail": "Mật khẩu cũ không đúng"}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        return Response({"detail": "Đổi mật khẩu thành công"}, status=status.HTTP_200_OK)

class PasswordReset(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        action_request = ActionRequest.objects.filter(token=token, available=True, expired_at__gt = datetime.now()).first()
        if action_request is None:
            return Response({"detail": "Token không hợp lệ"}, status=status.HTTP_400_BAD_REQUEST)
        
        user = action_request.user
        user.set_password(new_password)
        user.save()
        action_request.delete()
        return Response({"detail": "Đặt lại mật khẩu thành công"}, status=status.HTTP_200_OK)

class CameraStream(APIView):
    permission_classes = [AllowAny]
    def get(self, request, id):
        data, ts = get_camera_stream(id)
        if not data:
            raise Http404("Không có ảnh cho ID này")
        resp = HttpResponse(data, content_type="image/jpeg")
        resp["X-Timestamp"] = str(ts or 0)
        return resp
    
    def put(self, request, id):
        serializer = CameraStreamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        data = image.read()
        ts = int(time.time())
        update_camera_stream(id, data, ts)
        return Response({"ok": True, "id": id, "timestamp": ts}, status=status.HTTP_200_OK)

class ImageProcess(APIView):
    def post(self, request):
        imageProcessSerializer = ImageProcessSerializer(data=request.data)
        imageProcessSerializer.is_valid(raise_exception=True)

        exam_id = request.data.get('exam', None)
        examinee_id = request.data.get('examinee', None)
        exam = Exam.objects.filter(pk=exam_id).first() if exam_id else None
        examinee = Examinee.objects.filter(pk=examinee_id).first() if examinee_id else None

        examineeRecord = ExamineeRecord.objects.filter(exam=exam, examinee=examinee).first() if exam and examinee else None
        if not examineeRecord:
            return Response({"detail": "Không tìm thấy bản ghi thí sinh"}, status=status.HTTP_400_BAD_REQUEST)
        
        image_name = examineeRecord.img_before_process if examineeRecord else None
        if not image_name:
            return Response({"detail": "Không tìm thấy hình ảnh để xử lý"}, status=status.HTTP_400_BAD_REQUEST)
        
        result = process_image(image_name)
        if not result:
            return Response({"detail": "Xử lý hình ảnh thất bại"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(result, status=200)
    
class ImageProcessSave(APIView):
    def post(self, request):
        # Nhận result của ImageProcess (sau khi client xác nhận và chỉnh sửa nếu cần)
        serializer = ImageProcessSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exam_id = request.data.get('exam', None)
        examinee_id = request.data.get('examinee', None)
        exam = Exam.objects.filter(pk=exam_id).first() if exam_id else None
        examinee = Examinee.objects.filter(pk=examinee_id).first() if examinee_id else None
        result = serializer.validated_data.get('result', {})

        examineeRecord = ExamineeRecord.objects.filter(exam=exam, examinee=examinee, examinee_code=result.get('sbd', None)).first() if exam and examinee else None
        if not examineeRecord:
            return Response({"detail": "Không tìm thấy bản ghi thí sinh"}, status=status.HTTP_400_BAD_REQUEST)

        # Lấy đề thi từ ExamPaper
        exam_paper = ExamPaper.objects.filter(exam=exam, exam_paper_code=result.get('made', None)).first()
        if not exam_paper:
            return Response({"detail": "Không tìm thấy đề thi"}, status=status.HTTP_400_BAD_REQUEST)

        # Lấy đáp án đúng từ ExamAnswer
        correct_answers = ExamAnswer.objects.filter(exam_paper=exam_paper)
        correct_answer_dict = {ans.question_number: ans.answer_number for ans in correct_answers}

        # Kiểm tra và lưu đáp án vào ExamineePaper
        with transaction.atomic():
            correct_count = 0
            for q_num_str, ans_char in result.get('answers', {}).items():
                question_number = int(q_num_str)
                answer_number = ord(ans_char) - ord('A') if ans_char != '?' else 0
                mark_result = False
                if question_number in correct_answer_dict and answer_number == correct_answer_dict[question_number]:
                    correct_count += 1
                    mark_result = True
                axaminee_answer = ExamineePaper.objects.filter(exam_paper=exam_paper, examinee=examinee, question_number=question_number).first()
                if axaminee_answer:
                    axaminee_answer.answer_number = answer_number
                    axaminee_answer.mark_result = mark_result
                    axaminee_answer.save()
                    continue
                examinee_answer = ExamineePaper(exam_paper=exam_paper, examinee=examinee, question_number=question_number, answer_number=answer_number, mark_result=mark_result)
                examinee_answer.save()

            # Tính điểm
            score = (correct_count / exam_paper.number_of_questions) * 10 if exam_paper.number_of_questions > 0 else 0
            
            # Cập nhật ExamineeRecord
            if examineeRecord:
                examineeRecord.score = score
                examineeRecord.save()

        return Response({"detail": "Lưu kết quả bài thi thành công"}, status=status.HTTP_200_OK)
        