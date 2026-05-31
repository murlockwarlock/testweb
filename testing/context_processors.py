from django.utils import timezone
from .models import AppConfig


def project_context(request):
    try:
        config = AppConfig.load()
    except:
        config = None

    return {
        'current_year': timezone.now().year,
        'project_name': 'Я ПРОФИ',
        'app_config': config
    }