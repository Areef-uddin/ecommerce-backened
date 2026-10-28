from django.urls import path
from .views import (
    generate_tryon_view,
    tryon_job_detail_view,
    tryon_history_view,
    delete_tryon_job_view,
)

urlpatterns = [
    path('generate/', generate_tryon_view, name='tryon-generate'),
    path('jobs/<int:job_id>/', tryon_job_detail_view, name='tryon-job-detail'),
    path('history/', tryon_history_view, name='tryon-history'),
    path('history/<int:job_id>/', delete_tryon_job_view, name='tryon-history-delete'),
]

