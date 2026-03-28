from django.urls import path
from .views import (
    StudyMaterialAIChatView,
    StudyMaterialRecordDownloadView,
    StudyMaterialRecordViewView,
    StudyMaterialUpdateDeleteView,
    StudyMaterialUploadView,
)

app_name = 'study_materials'

urlpatterns = [
    path('upload/', StudyMaterialUploadView.as_view(), name='upload_material'),
    path('ai/chat/', StudyMaterialAIChatView.as_view(), name='ai_chat'),
    path('<int:material_id>/', StudyMaterialUpdateDeleteView.as_view(), name='material_update_delete'),
    path(
        '<int:material_id>/record-download/',
        StudyMaterialRecordDownloadView.as_view(),
        name='record_download',
    ),
    path(
        '<int:material_id>/record-view/',
        StudyMaterialRecordViewView.as_view(),
        name='record_view',
    ),
]
