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
from django.http import Http404, StreamingHttpResponse, HttpResponse
from django.db import transaction
from django.core.cache import cache

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
            raise Http404("Examinee not found")
        serializer = ExamineeRecordDetailSerializer(examinee)
        return Response(serializer.data, status=status.HTTP_200_OK)

# POST ExamPaper's Answer using JSON
class ExamPaperBatchAnswerView(APIView):
    serializer_class = ExamPaperBatchAnswerSerializer
    def post(self, request, exam_paper_pk):
        exam_paper = ExamPaper.objects.filter(pk=exam_paper_pk).first()
        if not exam_paper:
            raise Http404("ExamPaper not found")
        
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

class SendOTPForVerifyView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = SendOTPForVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        action = serializer.validated_data['action']
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "Email không tồn tại"}, status=status.HTTP_400_BAD_REQUEST)
        action_request = ActionRequest.objects.filter(
            user = user,
            available = False,
            expired_at__gt = datetime.now(),
            action=action
        ).first()

        if action_request is None:
            token = ''.join(map(str, [randomX.base62[x] for x in randomX.randomX(24, 0, 62)]))
            action_request = ActionRequest(user=user, token=token, action=action, expired_at=datetime.now() + timedelta(minutes=5), available=False)
            action_request.save()

        otp_code = randomX.randomOTP()
        otp_request = OTPRequest(code=otp_code, request=action_request, created_at=datetime.now(), expired_at=datetime.now() + timedelta(minutes=5))
        otp_request.save()

        serializer = OTPRequestSerializer(otp_request)

        send_otp.delay(action_request.user.email, otp_code)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
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

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
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

class ChangePasswordView(APIView):
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

class PasswordResetView(APIView):   
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

class CameraStreamView(APIView):
    permission_classes = [AllowAny]
    def mjpeg_generator(self, id):
        while True:
            data, ts = get_camera_stream(id)
            if data:
                frame = (
                    b"--testmarkdb\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + f"{len(data)}".encode() + b"\r\n"
                    b"\r\n" + data + b"\r\n"
                )
                yield frame
            time.sleep(1) # 1 FPS

    def get(self, request, id):
        return StreamingHttpResponse(
            self.mjpeg_generator(id),
           content_type="multipart/x-mixed-replace; boundary=testmarkdb"
        ) 

class CameraStreamImageView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, id):
        return HttpResponse(cache.get(key_value_data(id)), content_type="image/jpeg")
    
    def put(self, request, id):
        serializer = CameraStreamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        data = image.read()
        ts = int(time.time())
        update_camera_stream(id, data, ts)
        return Response({"ok": True, "id": id, "timestamp": ts}, status=status.HTTP_200_OK)

class ImageProcessView(APIView):
    def post(self, request):
        imageProcessSerializer = ImageProcessSerializer(data=request.data)
        imageProcessSerializer.is_valid(raise_exception=True)
        
        image = imageProcessSerializer.validated_data.get('image', None)
        if not image:
            return Response({"detail": "Không tìm thấy hình ảnh để xử lý"}, status=status.HTTP_400_BAD_REQUEST)

        # Lưu hình ảnh vào thư mục tạm thời
        os.makedirs(s3Image.BASE_DIR / "temporary", exist_ok=True)
        file_name = randomX.randomFileName()
        ext = os.path.splitext(image.name)[1]
        image.name = file_name + ext
        local_image_path = s3Image.BASE_DIR / "temporary" / image.name
        with open(local_image_path, "wb") as f:
            f.write(image.read())  
        
        # Xử lý hình ảnh
        result = process_image(image.name)
        if not result:
            return Response({"detail": "Xử lý hình ảnh thất bại"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(result, status=200)
    
class ImageProcessSaveView(APIView):
    def post(self, request):
        # Nhận result của ImageProcess (sau khi client xác nhận và chỉnh sửa nếu cần)
        serializer = ImageProcessSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam_id = request.data.get('exam', None)
        exam = Exam.objects.filter(pk=exam_id).first()
        if not exam:
            return Response({"detail": "Không tìm thấy kỳ thi"}, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.validated_data.get('result', {})

        student_ID = result.get('sbd', None)
        examinee = Examinee.objects.filter(user=request.user, student_ID=student_ID).first() if student_ID else None
        if not examinee:
            return Response({"detail": "Không tìm thấy thí sinh"}, status=status.HTTP_400_BAD_REQUEST)
        
        print(exam, examinee)
        examineeRecord = ExamineeRecord.objects.filter(exam=exam, examinee=examinee).first() if exam and examinee else None
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
            # Tải ảnh trước và sau xử lý lên S3
            before_image = result.get('original_image', None)
            if before_image:
                original_image_data = base64.b64decode(before_image)
                original_image = io.BytesIO(original_image_data)
                original_image.name = result.get('original_image_name', 'original_image.jpg')
                examineeRecord.original_image = upload_image(original_image)
            
            processed_image = result.get('processed_image', None)
            if processed_image:
                processed_image_data = base64.b64decode(processed_image)
                processed_image = io.BytesIO(processed_image_data)
                processed_image.name = result.get('processed_image_name', 'processed_image.jpg')
                examineeRecord.processed_image = upload_image(processed_image)
            
            # Lưu đáp án và đếm số câu đúng
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