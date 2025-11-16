from django.urls import include, path
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

router.register('Exams', ExamViewSet, basename='exam')
router.register('ExamPapers', ExamPaperViewSet, basename='exam_paper')
router.register('Examinees', ExamineeViewSet, basename='examinee')
router.register('ExamineeRecords', ExamineeRecordViewSet, basename='examinee_record')

exam_paper_router = routers.NestedSimpleRouter(router, 'Exams', lookup='exam')
exam_paper_router.register('Papers', ExamPaperViewSet, basename='exam_paper')

exam_answer_router = routers.NestedSimpleRouter(router, 'ExamPapers', lookup='exam_paper')
exam_answer_router.register('Answers', ExamAnswerViewSet, basename='exam_answer')

exam_record_router = routers.NestedSimpleRouter(router, 'Exams', lookup='exam')
exam_record_router.register('ExamineeRecords', ExamineeRecordViewSet, basename='examinee_record')

urlpatterns = [
    path("api/Register/", RegisterView.as_view(), name="Register"),
    
    path("api/SendOTPForEmailVerify/", SendOTPForEmailVerify.as_view(), name="SendOTPForEmailVerify"),
    path("api/VerifyOTP/", VerifyOTP.as_view(), name="VerifyOTP"),
    path("api/VerifyEmail/", VerifyEmail.as_view(), name="VerifyEmail"),
    path("api/ChangePassword/", ChangePassword.as_view(), name="ChangePassword"),
    
    path("api/CameraStream/<str:id>/", CameraStream.as_view(), name="CameraStream"),
    path("api/ImageProcess/", ImageProcess.as_view(), name="ImageProcess"),
    path("api/ImageProcessSave/", ImageProcessSave.as_view(), name="ImageProcessSave"),
    path("api/Examinee/<int:examinee_id>/RecordsDetail/", ExamineeRecordDetailView.as_view(), name="ExamineeRecordDetail"),
    path("api/ExamineeRecords/<int:examinee_record_pk>/Result/", ExamineeResultViewSet.as_view({'get': 'list'}), name="ExamineeResult"),
    path("api/ExamPapers/<int:exam_paper_pk>/BatchAnswer/", ExamPaperBatchAnswerView.as_view(), name="ExamPaperBatchAnswer"),

    path("api/", include(router.urls)),
    path("api/", include(exam_paper_router.urls)),
    path("api/", include(exam_answer_router.urls)),
    path("api/", include(exam_record_router.urls)),
]