from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone is required')
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Номер телефона",
        help_text="Основной идентификатор пользователя (формат +79XXXXXXXXX)."
    )
    first_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Имя",
        help_text="Имя владельца аккаунта."
    )
    security_question = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Секретный вопрос",
        help_text="Используется для восстановления доступа."
    )
    security_answer = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ответ на секретный вопрос",
        help_text="Хранится в открытом виде для сравнения при сбросе."
    )
    telegram_chat_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Telegram Chat ID",
        help_text="ID чата для отправки результатов."
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Позволяет пользователю входить в систему."
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name="Доступ в админку",
        help_text="Определяет, может ли пользователь заходить в эту панель управления."
    )
    consent_given = models.BooleanField(
        default=False,
        verbose_name="Согласие на рассылку",
        help_text="Факт принятия юридической оферты."
    )
    consent_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата согласия"
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата регистрации"
    )

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.phone

class SMSCode(models.Model):
    phone = models.CharField(max_length=20, verbose_name="Номер телефона")
    code = models.CharField(max_length=6, verbose_name="Код подтверждения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")

    class Meta:
        verbose_name = "SMS-код"
        verbose_name_plural = "SMS-коды"

    def is_valid(self):
        return self.created_at >= timezone.now() - timezone.timedelta(minutes=5)