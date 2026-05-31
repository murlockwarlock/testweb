import os
import telebot
import struct
import hmac
import hashlib
import base64
import time
import random
import json
import threading
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError
from django.core.serializers.json import DjangoJSONEncoder
from users.models import User
from testing.models import AppConfig, TestSuite, TestResult, Question, FinalQuestion
from testing.services import CoreService, PDFService
from testing.tasks import generate_ai_profile_task, send_telegram_result_task

def execute_stress_test(bot, chat_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_filename = f'full_ai_personalized_report_{timestamp}.json'
    config_filename = f'test_settings_v2_{timestamp}.json'
    results_path = f'/var/testweb/{results_filename}'
    config_path = f'/var/testweb/{config_filename}'

    try:
        suite = TestSuite.objects.get(pk=5)
    except TestSuite.DoesNotExist:
        bot.send_message(chat_id, "❌ Ошибка: Тест V2 (ID 5) не найден.")
        return

    suite_data = {
        "id": suite.pk,
        "name": suite.name,
        "version": suite.version,
        "prompts": {
            "profile_system": suite.profile_system_prompt,
            "report_system": suite.report_system_prompt,
            "profile_user": suite.profile_prompt,
            "short_user": suite.short_result_prompt,
            "extended_user": suite.extended_result_prompt
        },
        "categories": list(suite.categories.all().values('name', 'formula')),
        "reliability_rules": list(suite.reliability_rules.all().values('rule_type', 'threshold', 'error_message')),
        "final_questions": list(suite.final_questions.all().values('text', 'order'))
    }

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(suite_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    user, _ = User.objects.get_or_create(phone='+79990000000', defaults={'first_name': 'TEST_BOT'})
    questions = Question.objects.filter(suite=suite).order_by('order')
    final_questions = suite.final_questions.all().order_by('order')

    scenarios = [
        {
            "name": "TEST_STRATEG", "focus": [1, 13, 16, 6, 7, 4],
            "data": {
                "hobby": "Шахматы, программирование на Python",
                "subjects": "Математика, Информатика, Физика",
                "dream": "Создать глобальную IT-корпорацию",
                "future": "Вижу себя техническим директором крупного проекта",
                "skills": "Аналитическое мышление, стратегическое планирование",
                "activity": "Участие в хакатонах и олимпиадах по логике"
            }
        },
        {
            "name": "TEST_ENGINEER", "focus": [1, 13, 16, 5, 20],
            "data": {
                "hobby": "Разборка техники, LEGO Technic, 3D-печать",
                "subjects": "Технология, Геометрия, Физика",
                "dream": "Спроектировать экологичный двигатель",
                "future": "Инженер-конструктор в бюро",
                "skills": "Работа руками, понимание чертежей",
                "activity": "Кружок робототехники"
            }
        },
        {
            "name": "TEST_PIONEER", "focus": [2, 3, 12, 6, 7],
            "data": {
                "hobby": "Ведение блога, публичные выступления",
                "subjects": "Обществознание, История, Иностранный язык",
                "dream": "Стать лидером мнений в своей нише",
                "future": "Руководитель собственного стартапа",
                "skills": "Харизма, убеждение, инициативность",
                "activity": "Школьный совет, организация праздников"
            }
        },
        {
            "name": "TEST_RESEARCHER", "focus": [14, 1, 13, 16],
            "data": {
                "hobby": "Микроскопия, чтение научных журналов",
                "subjects": "Биология, Химия, География",
                "dream": "Открыть новый закон природы",
                "future": "Ученый-исследователь в лаборатории",
                "skills": "Внимательность к деталям, терпение",
                "activity": "Научное сообщество, полевые исследования"
            }
        },
        {
            "name": "TEST_CONSTRUCTOR", "focus": [15, 2, 11, 12, 5],
            "data": {
                "hobby": "Рисование, моделирование зданий из картона",
                "subjects": "МХК, ИЗО, Черчение",
                "dream": "Построить самое красивое здание в мире",
                "future": "Главный архитектор города",
                "skills": "Пространственное воображение, чувство стиля",
                "activity": "Художественная школа, дизайн интерьеров"
            }
        },
        {
            "name": "TEST_MEDIATOR", "focus": [8, 9, 10, 11, 19],
            "data": {
                "hobby": "Волонтерство, психология, помощь людям",
                "subjects": "Литература, Психология, Биология человека",
                "dream": "Сделать мир добрее и справедливее",
                "future": "Психотерапевт или HR-директор",
                "skills": "Эмпатия, умение слушать и договариваться",
                "activity": "Помощь в приютах, школьное медиаторство"
            }
        },
        {
            "name": "TEST_PRODUCER", "focus": [15, 2, 11, 6, 7],
            "data": {
                "hobby": "Монтаж видео, театральный кружок",
                "subjects": "Литература, Музыка, История",
                "dream": "Получить Оскар за лучший фильм",
                "future": "Режиссер или продюсер шоу",
                "skills": "Креативность, организаторские способности",
                "activity": "Школьный театр, ведение YouTube-канала"
            }
        },
        {
            "name": "TEST_EXPERT_LOGIC", "focus": [1, 13, 16],
            "data": {
                "hobby": "Решение математических головоломок",
                "subjects": "Алгебра, Геометрия, Информатика",
                "dream": "Разработать невзламываемый алгоритм",
                "future": "Специалист по кибербезопасности",
                "skills": "Абстрактное мышление, поиск ошибок",
                "activity": "Математические бои, программирование"
            }
        },
        {
            "name": "TEST_RANDOM_1", "focus": [],
            "data": {
                "hobby": "Киберспорт, Minecraft, Roblox",
                "subjects": "Физкультура, Труд, ОБЖ",
                "dream": "Выиграть международный турнир",
                "future": "Профессиональный геймер или стример",
                "skills": "Скорость реакции, работа в команде",
                "activity": "Компьютерные клубы"
            }
        },
        {
            "name": "TEST_RANDOM_2", "focus": [],
            "data": {
                "hobby": "Путешествия, изучение языков по песням",
                "subjects": "География, Английский, Литература",
                "dream": "Посетить все страны мира",
                "future": "Переводчик или тревел-блогер",
                "skills": "Общительность, адаптивность",
                "activity": "Языковые лагеря"
            }
        },
    ]

    created_ids = []
    bot.send_message(chat_id, f"🏁 Запуск полной проверки ({len(scenarios)} сценариев)...")

    for scenario in scenarios:
        answers = []
        for idx, q in enumerate(questions):
            q_num = idx + 1
            if q_num in scenario['focus']:
                score = 5
            elif not scenario['focus']:
                score = random.randint(1, 5)
            else:
                score = random.randint(1, 2)
            answers.append({'question': q.text, 'score': str(score)})

        extra_stats = {}
        for fq in final_questions:
            q_txt = fq.text.lower()
            val = "Тестовый ответ"

            if any(k in q_txt for k in ["предмет", "активн", "школ", "учеб"]):
                val = scenario['data']['subjects']
            elif any(k in q_txt for k in ["хобби", "увлеч", "заним", "свободн"]):
                val = scenario['data']['hobby']
            elif any(k in q_txt for k in ["мечта", "цель", "хочешь", "хотел"]):
                val = scenario['data']['dream']
            elif any(k in q_txt for k in ["будущ", "кем", "через", "професс"]):
                val = scenario['data']['future']
            elif any(k in q_txt for k in ["навык", "умеешь", "сильн", "способн"]):
                val = scenario['data']['skills']
            elif any(k in q_txt for k in ["меропр", "круж", "секц", "чем"]):
                val = scenario['data']['activity']

            extra_stats[fq.text] = val

        indices = CoreService.calculate_test_indices(answers, suite)
        rel_level, rel_notes = CoreService.calculate_reliability(answers, suite)

        res = TestResult.objects.create(
            user=user,
            suite=suite,
            child_name=scenario['name'],
            child_gender='male',
            child_age=14,
            answers_data=answers,
            extra_stats=extra_stats,
            calculated_indices=indices,
            reliability_level=rel_level,
            reliability_notes=rel_notes,
            short_interpretation="",
            extended_interpretation="",
            manager_info=""
        )
        created_ids.append(res.pk)
        generate_ai_profile_task.delay(res.pk, is_initial=True)

    bot.send_message(chat_id, "⏳ Ожидание ответов от нейросети... (может занять 15-20 минут)")

    start_time = time.time()
    last_count = -1

    while True:
        finished = TestResult.objects.filter(pk__in=created_ids).exclude(extended_interpretation="").exclude(
            extended_interpretation="Technical Test")
        count = finished.count()

        if count != last_count:
            bot.send_message(chat_id, f"🔄 Обработано ИИ: {count} из 10...")
            last_count = count

        if count == 10 or (time.time() - start_time > 1800):
            break
        time.sleep(30)

    for r in TestResult.objects.filter(pk__in=created_ids):
        short_pdf = PDFService.generate_pdf(r, report_type='short')
        full_pdf = PDFService.generate_pdf(r, report_type='full')

        bot.send_document(chat_id, short_pdf, visible_file_name=f"Short_{r.child_name}.pdf",
                          caption=f"📄 Краткий отчет: {r.child_name}")
        bot.send_document(chat_id, full_pdf, visible_file_name=f"Full_{r.child_name}.pdf",
                          caption=f"📑 Полный отчет: {r.child_name}")

    export_data = []
    for r in TestResult.objects.filter(pk__in=created_ids):
        export_data.append({
            "id": r.pk,
            "scenario": r.child_name,
            "profile": r.thinking_profile,
            "indices": r.calculated_indices,
            "extra_data_used": r.extra_stats,
            "ai_report_full": r.extended_interpretation
        })

    with open(config_path, 'rb') as f:
        bot.send_document(chat_id, f, caption=f"⚙️ Настройки теста V2\nФайл: {config_filename}")

    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    with open(results_path, 'rb') as f:
        bot.send_document(chat_id, f, caption=f"✨ Проверка завершена!\nФайл: {results_filename}")


class Command(BaseCommand):
    help = 'Запуск Telegram бота'

    def handle(self, *args, **options):
        config = AppConfig.load()
        if not config.telegram_bot_token:
            self.stdout.write(self.style.ERROR('Токен Telegram бота не задан в настройках'))
            return

        bot = telebot.TeleBot(config.telegram_bot_token)
        signer = TimestampSigner()

        @bot.message_handler(commands=['stress_test_start'])
        def handle_stress_test(message):
            bot.reply_to(message, "🚀 Секретная команда принята. Начинаю фоновый стресс-тест...")
            threading.Thread(target=execute_stress_test, args=(bot, message.chat.id)).start()

        @bot.message_handler(commands=['start'])
        def handle_start(message):
            try:
                args = message.text.split()
                user = None
                is_new_link = False

                if len(args) > 1:
                    token = args[1]
                    try:
                        token += '=' * (-len(token) % 4)
                        token_bytes = base64.urlsafe_b64decode(token)

                        if len(token_bytes) == 20:
                            data = token_bytes[:8]
                            received_sig = token_bytes[8:]

                            calc_sig = hmac.new(
                                settings.SECRET_KEY.encode(),
                                data,
                                hashlib.sha256
                            ).digest()[:12]

                            if hmac.compare_digest(received_sig, calc_sig):
                                user_id, timestamp = struct.unpack('>II', data)
                                if time.time() - timestamp < 86400:
                                    user = User.objects.get(pk=user_id)
                                    is_new_link = True
                    except Exception:
                        pass

                if user:
                    already_linked = (user.telegram_chat_id == str(message.chat.id))
                    user.telegram_chat_id = str(message.chat.id)

                    try:
                        user.save()
                    except IntegrityError:
                        bot.reply_to(message,
                                     "⛔ <b>Ошибка привязки!</b>\n\nЭтот Telegram-аккаунт уже привязан к другому пользователю сайта. Нельзя использовать один Telegram для нескольких аккаунтов.",
                                     parse_mode='HTML')
                        return

                    if not already_linked or is_new_link:
                        greeting_name = f", {user.first_name}" if user.first_name else ""
                        bot.reply_to(message,
                                     f"✅ Аккаунт подтвержден! Здравствуйте{greeting_name}!\nСейчас пришлю ваш результат.")

                        from testing.models import TestResult

                        last_result = TestResult.objects.filter(user=user).order_by('-created_at').first()

                        if last_result:
                            if not last_result.short_interpretation:
                                bot.send_message(message.chat.id,
                                                 "⏳ <b>Отчет обрабатывается...</b>\nПожалуйста, подождите. Как только он будет готов, файл придет сюда автоматически.",
                                                 parse_mode='HTML')
                            else:
                                bot.send_message(message.chat.id, "📄 Формирую PDF-файл...")
                                send_telegram_result_task.delay(last_result.pk, report_type='short')
                        else:
                            bot.send_message(message.chat.id,
                                             "Результаты тестирования не найдены. Пройдите тест на сайте.")

                    else:
                        bot.send_message(message.chat.id,
                                         "👋 Мы уже знакомы! Если вы пройдете новый тест, результат придет сюда автоматически.")

                else:
                    if len(args) > 1:
                        bot.reply_to(message, "❌ Ссылка устарела или некорректна.")
                    elif User.objects.filter(telegram_chat_id=str(message.chat.id)).exists():
                        bot.reply_to(message,
                                     "👋 Вы уже подписаны на обновления. Если вы прошли новый тест, PDF придет автоматически.")
                    else:
                        bot.reply_to(message, "Для привязки аккаунта перейдите по ссылке из Личного Кабинета на сайте.")

            except Exception as e:
                bot.reply_to(message, f"Произошла ошибка: {str(e)}")

        @bot.message_handler(commands=['login'])
        def handle_login(message):
            try:
                user = User.objects.filter(telegram_chat_id=str(message.chat.id)).first()
                if not user:
                    bot.reply_to(message, "Сначала привяжите аккаунт через сайт.")
                    return

                token = signer.sign(user.pk)
                domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else '127.0.0.1:8000'
                protocol = 'https' if not settings.DEBUG else 'http'
                link = f"{protocol}://{domain}/magic-login/{token}/"

                bot.reply_to(message, f"🔑 <b>Магическая ссылка для входа:</b>\n\n{link}\n\n(Действительна 5 минут)",
                             parse_mode='HTML')
            except Exception:
                bot.reply_to(message, "Ошибка генерации ссылки")

        @bot.message_handler(commands=['reset'])
        def handle_reset(message):
            try:
                user = User.objects.filter(telegram_chat_id=str(message.chat.id)).first()
                if not user:
                    bot.reply_to(message, "Аккаунт не найден.")
                    return

                token = signer.sign(user.phone)
                domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else '127.0.0.1:8000'
                protocol = 'https' if not settings.DEBUG else 'http'
                link = f"{protocol}://{domain}/tg-reset/{token}/"

                bot.reply_to(message,
                             f"🔄 <b>Сброс пароля:</b>\n\n{link}\n\nПерейдите по ссылке, чтобы задать новый пароль.",
                             parse_mode='HTML')
            except Exception:
                bot.reply_to(message, "Ошибка генерации ссылки")

        @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_report_'))
        def handle_buy_report(call):
            try:
                result_pk = call.data.split('_')[2]
                result = TestResult.objects.get(pk=result_pk)

                from django.core.cache import cache

                # Проверка, не оплачено ли уже
                if result.is_paid:
                    lock_key = f"tg_send_lock_{result.pk}_full"
                    if cache.get(lock_key):
                        bot.answer_callback_query(call.id, "Отчет уже отправляется, проверьте чат!", show_alert=False)
                        return
                    cache.set(lock_key, True, timeout=120)
                    bot.answer_callback_query(call.id, "Отчет уже оплачен! Отправляю...")
                    send_telegram_result_task.delay(result.pk, report_type='full')
                    return

                # Удаляем предыдущее платёжное сообщение (ссылка могла устареть)
                old_pay_msg_id = cache.get(f"tg_pay_msg_{result.pk}")
                if old_pay_msg_id:
                    cache.delete(f"tg_pay_msg_{result.pk}")
                    try:
                        bot.delete_message(call.message.chat.id, old_pay_msg_id)
                    except Exception:
                        pass

                # Генерация ссылки
                from testing.services import TochkaPaymentService
                payment_link = TochkaPaymentService.create_payment_link(result)

                config = AppConfig.load()

                msg = (
                    f"💳 <b>Оплата отчета для: {result.child_name}</b>\n"
                    f"Стоимость: {config.payment_price} ₽\n\n"
                    f"Для оплаты перейдите по ссылке ниже. После успешной оплаты полный отчет придет сюда автоматически."
                )

                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton(text="👉 Перейти к оплате", url=payment_link))

                sent_pay = bot.send_message(call.message.chat.id, msg, parse_mode='HTML', reply_markup=markup)
                # Сохраняем ID, чтобы удалить сообщение после оплаты
                cache.set(f"tg_pay_msg_{result.pk}", sent_pay.message_id, timeout=86400 * 7)
                bot.answer_callback_query(call.id)

            except Exception as e:
                bot.answer_callback_query(call.id, "Ошибка создания ссылки")
                bot.send_message(call.message.chat.id, f"Произошла ошибка при создании платежа: {e}")

        bot.set_my_commands([
            telebot.types.BotCommand("start", "Запуск / Привязка аккаунта"),
            telebot.types.BotCommand("login", "Вход в личный кабинет"),
            telebot.types.BotCommand("reset", "Сброс пароля"),
        ])

        self.stdout.write(self.style.SUCCESS('Бот запущен...'))
        bot.infinity_polling()