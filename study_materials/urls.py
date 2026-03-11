from django.urls import path
from .views import StudyMaterialUploadView

app_name = 'study_materials'

urlpatterns = [
    path('upload/', StudyMaterialUploadView.as_view(), name='upload_material'),
]
