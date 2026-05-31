from django.contrib.auth.backends import BaseBackend
from .models import User


class SMSBackend(BaseBackend):
    def authenticate(self, request, phone=None, **kwargs):
        if phone is None:
            return None

        try:
            return User.objects.get(phone=phone)
        except User.DoesNotExist:
            return User.objects.create_user(phone=phone)

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None