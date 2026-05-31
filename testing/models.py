from django.db import models
from django.conf import settings
import os
from django.utils.text import slugify


def example_report_path(instance, filename):
    name, ext = os.path.splitext(filename)
    clean_name = slugify(name)
    if not clean_name:
        import uuid
        clean_name = str(uuid.uuid4())[:8]
    return os.path.join('examples', f"{clean_name}{ext}")

class AppConfig(models.Model):
    deepseek_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ключ DeepSeek API",
        help_text="Используется для связи с нейросетью."
    )
    ai_max_tokens_chat = models.PositiveIntegerField(
        default=4000,
        verbose_name="Max Tokens (Chat)",
        help_text="Лимит токенов для моделей типа Chat. Рекомендуется: 4000, максимум 8000."
    )
    ai_max_tokens_reasoner = models.PositiveIntegerField(
        default=32000,
        verbose_name="Max Tokens (Thinking-mode)",
        help_text="Лимит токенов для моделей типа thinking-mode. Рекомендуется: 32000, максимум 64000."
    )
    telegram_bot_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Токен Telegram бота",
        help_text="Получите у @BotFather. Пример: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    )
    telegram_bot_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Имя Telegram бота (без @)",
        help_text="Например: Humanprofibot. Нужно для формирования ссылки."
    )
    admin_notification_ids = models.TextField(
        blank=True,
        null=True,
        verbose_name="ID администраторов (Telegram)",
        help_text="Введите chat_id администраторов через запятую. Им будут приходить уведомления о заявках."
    )
    example_full_report = models.FileField(
        upload_to=example_report_path,
        blank=True,
        null=True,
        verbose_name="Пример полного отчета (PDF)",
        help_text="Загрузите файл примера. Если не загружено, кнопка может не работать."
    )
    is_payment_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить платный режим",
        help_text="Если включено, полный отчет доступен только после оплаты."
    )
    payment_price = models.PositiveIntegerField(
        default=0,
        verbose_name="Стоимость полного отчета (RUB)",
        help_text="Сумма в рублях, которую должен оплатить клиент."
    )
    tochka_jwt_token = models.TextField(
        blank=True,
        null=True,
        verbose_name="JWT Токен Точка Банка",
        help_text="Сгенерируйте в интернет-банке Точки (Интеграции и API -> JWT)."
    )
    tochka_customer_code = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Customer Code (Точка)",
        help_text="Уникальный код клиента в системе банка. Можно получить через API или в ЛК."
    )
    tochka_merchant_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Merchant ID (Точка)",
        help_text="Идентификатор торговой точки (15 цифр). Нужен для эквайринга."
    )
    tochka_client_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Client ID (Точка)",
        help_text="ID приложения. Нужен для проверки вебхуков и OAuth."
    )
    tochka_client_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Client Secret (Точка)",
        help_text="Секрет приложения. Нужен, если будете настраивать автоматическое получение токена."
    )
    support_project_name = models.CharField(
        max_length=255,
        default="Проект «Я ПРОФИ»",
        verbose_name="Название проекта (в поддержке)",
        blank=True
    )
    support_website = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Сайт проекта (URL)",
        help_text="Например: https://proftest.ru"
    )
    support_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Телефон поддержки",
        help_text="Например: +7 (900) 123-45-67"
    )
    support_telegram = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ссылка на Telegram канал",
        help_text="Например: https://t.me/proftest_channel"
    )
    support_whatsapp = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="WhatsApp (номер или ссылка)",
        help_text="Например: 79001234567 или https://wa.me/79001234567"
    )
    support_messenger_max = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Мессенджер MAX (ссылка)",
        help_text="Введите ссылку на чат в мессенджере MAX"
    )
    support_instagram = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Instagram (ссылка)",
        help_text="Например: https://instagram.com/username"
    )
    support_email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Электронная почта",
        help_text="Например: support@proftest.ru"
    )

    class Meta:
        verbose_name = "Настройки системы"
        verbose_name_plural = "Настройки системы"

    def __str__(self):
        return "Глобальные параметры API и контакты"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(AppConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class TestSuite(models.Model):
    MODEL_CHOICES = [
        ('deepseek-chat', 'DeepSeek (Chat)'),
        ('deepseek-reasoner', 'DeepSeek (Thinking-mode)'),
    ]

    name = models.CharField(max_length=255, verbose_name="Название теста", default="Основной тест")
    version = models.CharField(
        max_length=10,
        choices=[
            ('V0', 'Дошкольники (5-7 лет)'),
            ('V1', 'Школьники (7-11 лет)'),
            ('V2', 'Подростки (12-17 лет)'),
            ('V3', 'Взрослые (18+ лет)')
        ],
        default='V1',
        verbose_name="Версия"
    )

    example_pdf_male = models.FileField(
        upload_to=example_report_path,
        blank=True,
        null=True,
        verbose_name="Пример отчета (Мальчики/Мужчины)",
        help_text="PDF файл примера для этой версии (М)"
    )
    example_pdf_female = models.FileField(
        upload_to=example_report_path,
        blank=True,
        null=True,
        verbose_name="Пример отчета (Девочки/Женщины)",
        help_text="PDF файл примера для этой версии (Ж)"
    )

    profile_system_prompt = models.TextField(
        verbose_name="System Prompt для профиля",
        default="Ты — эксперт по профориентации. Определи профиль мышления на основе данных."
    )
    report_system_prompt = models.TextField(
        verbose_name="System Prompt для отчетов",
        default="Ты — профессиональный психолог-диагност. Пишешь подробный отчет для ребенка."
    )

    profile_prompt = models.TextField(blank=True, null=True, verbose_name="User Prompt для профиля")
    short_result_prompt = models.TextField(blank=True, null=True, verbose_name="User Prompt для краткого отчета")
    extended_result_prompt = models.TextField(blank=True, null=True, verbose_name="User Prompt для полного отчета")
    manager_prompt = models.TextField(blank=True, null=True, verbose_name="User Prompt для менеджера")

    ai_model_profile = models.CharField(max_length=50, choices=MODEL_CHOICES, default='deepseek-chat',
                                        verbose_name="Модель для профиля")
    ai_model_report = models.CharField(max_length=50, choices=MODEL_CHOICES, default='deepseek-reasoner',
                                       verbose_name="Модель для отчетов")
    ai_temperature = models.FloatField(default=0.1, verbose_name="Температура AI (0.0 - 1.0)")

    send_child_name = models.BooleanField(default=True, verbose_name="Имя ребенка {{child_name}}")
    send_child_info = models.BooleanField(default=True, verbose_name="Возраст {{child_age}} и пол {{child_gender}}")
    send_indices = models.BooleanField(default=True, verbose_name="Результаты формул {{indices}}")
    send_thinking_profile = models.BooleanField(default=True, verbose_name="Профиль мышления {{profile}}")
    send_extra_data = models.BooleanField(default=True, verbose_name="Дополнительные вопросы {{extra_data}}")
    send_reliability = models.BooleanField(default=True, verbose_name="Достоверность {{reliability}}")
    send_answers_data = models.BooleanField(default=False, verbose_name="Все ответы и вопросы {{answers_data}}")
    send_rag_context = models.BooleanField(default=True, verbose_name="База знаний (RAG) {{rag_context}}")
    send_location = models.BooleanField(default=False, verbose_name="Локация ребёнка {{location}}")
    send_school_info = models.BooleanField(default=True, verbose_name="Школа и класс {{school}}, {{grade}}")
    send_parent_info = models.BooleanField(default=False,
                                           verbose_name="Данные родителя {{parent_name}}, {{parent_phone}}")
    send_project_info = models.BooleanField(default=True, verbose_name="Данные проекта {{project_name}}, {{website}}")
    send_test_meta = models.BooleanField(default=True, verbose_name="Метаданные теста {{test_date}}, {{test_version}}")

    description = models.TextField(blank=True, verbose_name="Вводный текст (HTML)")
    closing_text = models.TextField(blank=True, verbose_name="Заключительный текст (HTML)")
    scale_config = models.JSONField(default=dict, blank=True, verbose_name="Настройки шкалы")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_admin_only = models.BooleanField(default=False, verbose_name="Только для админов (Тестовый режим)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Версия теста"
        verbose_name_plural = "Версии тестов"

    def __str__(self):
        return f"{self.name} ({self.version})"


class Question(models.Model):
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Тест",
        help_text="Набор, к которому относится этот вопрос."
    )
    text = models.TextField(
        verbose_name="Текст вопроса",
        help_text="Утверждение, которое пользователь должен оценить."
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядковый номер",
        help_text="Определяет очередность вывода вопросов."
    )
    category = models.ForeignKey(
        'TestCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
        verbose_name="Категория (Индекс)"
    )

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ['order']

    def __str__(self):
        return self.text[:50]

    def save(self, *args, **kwargs):
        if self.order == 0:
            last_question = Question.objects.filter(suite=self.suite).order_by('-order').first()
            if last_question:
                self.order = last_question.order + 1
            else:
                self.order = 1
        super().save(*args, **kwargs)


class TestResult(models.Model):
    CONTACT_METHODS = [
        ('telegram', 'Telegram Бот'),
        ('email', 'E-mail'),
        ('max', 'Мессенджер MAX'),
        ('view_only', 'Только просмотр'),
    ]
    location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Местонахождение"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь (родитель)",
        help_text="Аккаунт, с которого пройдено тестирование."
    )
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        verbose_name="Использованный тест",
        help_text="Версия теста, которую прошел ребенок."
    )
    child_name = models.CharField(
        max_length=255,
        verbose_name="Имя и фамилия ребёнка"
    )
    child_gender = models.CharField(
        max_length=10,
        verbose_name="Пол ребёнка"
    )
    child_dob = models.DateField(
        verbose_name="Дата рождения ребёнка",
        null=True,
        blank=True
    )
    child_age = models.IntegerField(
        verbose_name="Возраст"
    )
    school_number = models.CharField(
        max_length=50,
        verbose_name="Номер школы",
        blank=True
    )
    grade = models.CharField(
        max_length=20,
        verbose_name="Класс",
        blank=True
    )
    parent_name = models.CharField(
        max_length=255,
        verbose_name="Имя и фамилия родителя",
        blank=True
    )
    parent_phone = models.CharField(
        max_length=20,
        verbose_name="Контактный номер родителя",
        blank=True
    )
    answers_data = models.JSONField(
        verbose_name="Данные ответов"
    )
    extra_stats = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Дополнительная статистика"
    )
    calculated_indices = models.JSONField(
        default=dict,
        verbose_name="Рассчитанные индексы"
    )
    thinking_profile = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Профиль мышления"
    )
    reliability_level = models.CharField(
        max_length=10,
        default='green',
        verbose_name="Уровень достоверности"
    )
    reliability_notes = models.TextField(
        blank=True,
        verbose_name="Заметки по достоверности"
    )
    short_interpretation = models.TextField(
        blank=True,
        verbose_name="Краткое заключение (ИИ)"
    )
    extended_interpretation = models.TextField(
        blank=True,
        verbose_name="Полный отчет (ИИ)"
    )
    manager_info = models.TextField(
        blank=True,
        verbose_name="Информация для менеджера (ИИ)"
    )
    contact_method = models.CharField(
        max_length=20,
        choices=CONTACT_METHODS,
        default='view_only',
        verbose_name="Способ получения отчета"
    )
    contact_detail = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Контактные данные (Email/MAX)",
        help_text="Email или ссылка на профиль"
    )

    # --- ОПЛАТА ---
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Оплачен полный отчет"
    )
    payment_operation_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID операции оплаты (Точка)",
        help_text="operationId из банка"
    )
    promo_code = models.ForeignKey(
        'PromoCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Промокод",
        related_name='test_results'
    )
    # --------------

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата и время"
    )

    class Meta:
        verbose_name = "Результат тестирования"
        verbose_name_plural = "Результаты тестирований"

    def __str__(self):
        from django.utils import timezone
        dt = timezone.localtime(self.created_at)
        paid_mark = "💰 " if self.is_paid else ""
        return f"{paid_mark}ID {self.pk}: {self.child_name} — {dt.strftime('%d.%m.%Y %H:%M')} (МСК)"


class AIErrorLog(models.Model):
    result = models.ForeignKey('TestResult', on_delete=models.CASCADE, related_name='error_logs', null=True, blank=True)
    error_type = models.CharField(max_length=100, verbose_name="Тип ошибки")
    message = models.TextField(verbose_name="Текст ошибки")
    model_used = models.CharField(max_length=50, null=True, blank=True, verbose_name="Использованная модель")
    temp_used = models.FloatField(null=True, blank=True, verbose_name="Температура")
    raw_response = models.TextField(null=True, blank=True, verbose_name="Сырой ответ API")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лог ошибок ИИ"
        verbose_name_plural = "Логи ошибок ИИ"

    def __str__(self):
        return f"{self.error_type} - {self.created_at}"


class FinalQuestion(models.Model):
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name='final_questions',
        verbose_name="Тест"
    )
    text = models.TextField(
        verbose_name="Текст вопроса",
        help_text="Например: 'Какое у тебя хобби?' или 'Твоя мечта?'"
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок вывода"
    )

    class Meta:
        verbose_name = "Финальный вопрос"
        verbose_name_plural = "Финальные вопросы (после теста)"
        ordering = ['order']

    def __str__(self):
        return self.text


class TestCategory(models.Model):
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='categories', verbose_name="Тест")
    name = models.CharField(max_length=100, verbose_name="Название индекса")
    formula = models.CharField(
        max_length=255,
        verbose_name="Формула расчета",
        help_text="Используйте [q1], [q2] и т.д. Пример: ([q1]+[q5])/2 * 25. Это сложит баллы за 1 и 5 вопросы, найдет среднее и переведет в 100-балльную шкалу."
    )

    class Meta:
        verbose_name = "Категория (Индекс)"
        verbose_name_plural = "Категории (Индексы)"

    def __str__(self):
        return f"{self.name} ({self.suite.name})"


class ReliabilityRule(models.Model):
    RULE_TYPES = [
        ('inconsistency', 'Противоречивость (Разница баллов)'),
        ('both_high', 'Противоречивость (Оба высокие - Ловушка)'),
        ('social_desirability', 'Социальная желательность (Шкала лжи)'),
        ('fixed_answer', 'Проверочный вопрос (Внимание)'),
        ('monotony', 'Однообразие ответов (Случайный выбор)'),
    ]
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='reliability_rules',
                              verbose_name="Тест")
    rule_type = models.CharField(
        max_length=50,
        choices=RULE_TYPES,
        verbose_name="Тип проверки",
        help_text="Выберите, что именно мы проверяем."
    )
    question_indices = models.CharField(
        max_length=100,
        verbose_name="Номера вопросов",
        blank=True,
        null=True,
        help_text="Введите номера вопросов через запятую."
    )
    threshold = models.FloatField(
        default=0,
        verbose_name="Порог срабатывания",
        help_text="Порог срабатывания правила."
    )
    error_message = models.CharField(
        max_length=255,
        verbose_name="Текст замечания",
        help_text="Что увидит администратор в отчете."
    )
    severity = models.CharField(
        max_length=10,
        choices=[('yellow', 'Предупреждение (Желтый)'), ('red', 'Недостоверно (Красный)')],
        default='yellow',
        verbose_name="Уровень критичности",
        help_text="Для V1 влияет на цвет сразу. Для V2/V3 — просто фиксирует ошибку."
    )

    class Meta:
        verbose_name = "Правило достоверности"
        verbose_name_plural = "Правила достоверности"


class LandingPage(models.Model):
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок страницы",
        default="Профориентационное тестирование"
    )
    subtitle = models.TextField(
        blank=True,
        verbose_name="Подзаголовок (описание под заголовком)"
    )
    main_image = models.ImageField(
        upload_to='landing/',
        blank=True,
        null=True,
        verbose_name="Главное изображение",
        help_text="Используется, если не указано видео."
    )
    video_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="Ссылка на видео (YouTube)",
        help_text="Например: https://www.youtube.com/watch?v=ID_ВИДЕО"
    )
    content_html = models.TextField(
        blank=True,
        verbose_name="Основной контент (HTML)",
        help_text="Здесь можно разместить любую информацию."
    )
    button_text = models.CharField(
        max_length=50,
        default="Пройти тест",
        verbose_name="Текст на кнопке"
    )

    class Meta:
        verbose_name = "Конструктор лендинга"
        verbose_name_plural = "Конструктор лендинга"

    def __str__(self):
        return "Настройки страницы /test/"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(LandingPage, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class UtmCampaign(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название кампании")
    utm_source = models.CharField(max_length=100, verbose_name="utm_source")
    utm_medium = models.CharField(max_length=100, verbose_name="utm_medium", blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, verbose_name="utm_campaign", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "UTM-метка"
        verbose_name_plural = "UTM-метки"

    def __str__(self):
        return f"{self.name} ({self.utm_source})"


class UserUtm(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='utm_info')
    utm_source = models.CharField(max_length=100, blank=True, null=True)
    utm_medium = models.CharField(max_length=100, blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "UTM-данные пользователя"
        verbose_name_plural = "UTM-данные пользователей"


class KnowledgeBaseDocument(models.Model):
    file = models.FileField(
        upload_to='knowledge_base/',
        verbose_name="Файл документа",
        help_text="Поддерживаются PDF, DOCX, XLSX, TXT"
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    location = models.ForeignKey(
        'Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Локация",
        help_text="Если не выбрана — документ используется для всех регионов (глобальный)"
    )
    is_processed = models.BooleanField(default=False, verbose_name="Обработан")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    class Meta:
        verbose_name = "Документ базы знаний"
        verbose_name_plural = "База знаний (RAG)"

    def __str__(self):
        return self.title


class ProfileMatrix(models.Model):
    suite = models.ForeignKey('TestSuite', on_delete=models.CASCADE, related_name='profile_matrix', verbose_name="Тест")
    index_1 = models.ForeignKey('TestCategory', on_delete=models.CASCADE, related_name='matrix_index_1',
                                verbose_name="Индекс 1")
    index_2 = models.ForeignKey('TestCategory', on_delete=models.CASCADE, related_name='matrix_index_2',
                                verbose_name="Индекс 2")
    profile_name = models.CharField(max_length=100, verbose_name="Название профиля (напр. СТРАТЕГ)")

    class Meta:
        verbose_name = "Матрица профиля"
        verbose_name_plural = "Матрица профилей"

    def __str__(self):
        return f"{self.index_1.name} + {self.index_2.name} = {self.profile_name}"


class ProfileRecommendation(models.Model):
    suite = models.ForeignKey('TestSuite', on_delete=models.CASCADE, related_name='recommendations',
                              verbose_name="Тест")
    profile_name = models.CharField(max_length=100, verbose_name="Название профиля")
    description = models.TextField(verbose_name="Описание профиля")
    vector_development = models.TextField(verbose_name="Вектор развития (1-2 года)")
    top_professions = models.TextField(verbose_name="Топ-5 профессий (с описанием)")
    action_plan = models.TextField(verbose_name="План действий на 3 месяца")
    zones_attention = models.TextField(verbose_name="Зоны внимания (что может быть сложным)")

    class Meta:
        verbose_name = "Рекомендация профиля"
        verbose_name_plural = "Рекомендации профилей"

    def __str__(self):
        return f"Рекомендации для {self.profile_name}"


class Location(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название локации")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок вывода")

    class Meta:
        verbose_name = "Локация (Регион)"
        verbose_name_plural = "Локации (Регионы)"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('approved', 'Оплачено'),
        ('failed', 'Ошибка'),
        ('expired', 'Истекло'),
    ]

    result = models.ForeignKey(
        'TestResult',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Результат теста"
    )
    operation_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID операции (Точка)"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма (RUB)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    payment_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Ссылка на оплату"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    confirmed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата подтверждения"
    )

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']

    def __str__(self):
        return f"Платёж #{self.pk} — {self.get_status_display()} — {self.amount}₽"


class PromoCode(models.Model):
    DISCOUNT_TYPES = [
        ('free', 'Бесплатно (0 ₽)'),
        ('fixed_price', 'Фиксированная цена'),
    ]
    code = models.CharField(max_length=50, unique=True, verbose_name="Промокод")
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPES,
        default='fixed_price',
        verbose_name="Тип скидки"
    )
    fixed_price = models.PositiveIntegerField(
        default=0,
        verbose_name="Цена (₽)",
        help_text="Сумма к оплате. Только для типа «Фиксированная цена»."
    )
    max_uses = models.PositiveIntegerField(default=10, verbose_name="Макс. использований")
    used_count = models.PositiveIntegerField(default=0, verbose_name="Использовано")
    expires_at = models.DateTimeField(verbose_name="Действует до")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"

    def __str__(self):
        if self.discount_type == 'free':
            return f"{self.code} (бесплатно)"
        return f"{self.code} ({self.fixed_price} ₽)"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True

    @property
    def final_price(self):
        if self.discount_type == 'free':
            return 0
        return self.fixed_price


class ReportDelivery(models.Model):
    DELIVERY_METHODS = [
        ('auto_telegram', 'Авто (Telegram)'),
        ('manual_telegram', 'Ручная (Telegram)'),
        ('auto_webhook', 'Авто (Webhook/оплата)'),
        ('auto_fallback', 'Авто (Fallback)'),
    ]
    REPORT_TYPES = [
        ('short', 'Краткий'),
        ('full', 'Полный'),
    ]

    result = models.ForeignKey(
        'TestResult',
        on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name="Результат теста"
    )
    report_type = models.CharField(
        max_length=10,
        choices=REPORT_TYPES,
        verbose_name="Тип отчёта"
    )
    method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHODS,
        verbose_name="Способ отправки"
    )
    delivered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата отправки"
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Отправил (менеджер)",
        help_text="Заполняется при ручной отправке"
    )

    class Meta:
        verbose_name = "Отправка отчёта"
        verbose_name_plural = "Отправки отчётов"
        ordering = ['-delivered_at']

    def __str__(self):
        return f"{self.get_report_type_display()} — {self.get_method_display()} — {self.delivered_at:%d.%m.%Y %H:%M}"