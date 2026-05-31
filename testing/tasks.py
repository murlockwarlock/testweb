from celery import shared_task
from django.conf import settings
from django.urls import reverse
from .models import TestResult, KnowledgeBaseDocument, AIErrorLog, Payment
from .services import CoreService, RAGService, PDFService, TochkaPaymentService
import re
import traceback


def clean_html_for_telegram(raw_html):
    if not raw_html:
        return ""
    text = re.sub(r'<h[1-6]>(.*?)</h[1-6]>', r'<b>\1</b>\n', raw_html)
    text = text.replace('<p>', '').replace('</p>', '\n\n')
    text = text.replace('<ul>', '').replace('</ul>', '')
    text = text.replace('<ol>', '').replace('</ol>', '')
    text = text.replace('<li>', '• ').replace('</li>', '\n')
    text = text.replace('<hr>', '\n------------------\n').replace('<hr />', '\n------------------\n')
    text = text.replace('<br>', '\n').replace('<br />', '\n')
    return text.strip()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, max_retries=5)
def generate_extended_report_task(self, result_pk):
    try:
        result = TestResult.objects.get(pk=result_pk)
        ai_text = CoreService.get_ai_response(result_obj=result, is_extended=True)
        result.extended_interpretation = ai_text
        result.save(update_fields=['extended_interpretation'])

        result.refresh_from_db()  # оплата могла прийти пока шла генерация
        if result.is_paid:
            send_telegram_result_task.delay(result.pk, report_type='full')

        return f"Extended report for {result.child_name} SUCCESS"
    except Exception as e:
        res_obj = TestResult.objects.filter(pk=result_pk).first()
        AIErrorLog.objects.create(
            result=res_obj,
            error_type="EXTENDED_REPORT_TASK_ERROR",
            message=f"{str(e)}\n{traceback.format_exc()}"
        )
        # Уведомляем пользователя только если оплатил и все попытки исчерпаны
        if self.request.retries >= self.max_retries - 1:
            if res_obj and res_obj.is_paid and res_obj.user.telegram_chat_id:
                notify_ai_error_task.delay(result_pk, report_type='full')
        raise e


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=15, max_retries=5)
def generate_short_report_task(self, result_pk, automatic_send=False):
    from django.db import transaction
    try:
        result = TestResult.objects.get(pk=result_pk)
        ai_text = CoreService.get_ai_response(result_obj=result, is_extended=False)

        with transaction.atomic():
            result.short_interpretation = ai_text
            result.save(update_fields=['short_interpretation'])

        # ОБНОВЛЯЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ, ЧТОБЫ УВИДЕТЬ CHAT_ID, ЕСЛИ ОН ПОДКЛЮЧИЛСЯ ВО ВРЕМЯ ГЕНЕРАЦИИ
        result.user.refresh_from_db()

        if automatic_send and result.user.telegram_chat_id:
            send_telegram_result_task.delay(result.pk, report_type='short')

        return f"Short report for {result.child_name} SUCCESS"
    except Exception as e:
        res_obj = TestResult.objects.filter(pk=result_pk).first()
        AIErrorLog.objects.create(result=res_obj, error_type="SHORT_REPORT_TASK_ERROR",
                                  message=f"{str(e)}\n{traceback.format_exc()}")
        # Уведомляем пользователя если все попытки исчерпаны и бот подключён
        if self.request.retries >= self.max_retries - 1:
            if res_obj and res_obj.user.telegram_chat_id:
                notify_ai_error_task.delay(result_pk, report_type='short')
        raise e


@shared_task
def process_knowledge_base_document_task(doc_pk):
    try:
        doc = KnowledgeBaseDocument.objects.get(pk=doc_pk)
        text = RAGService.extract_text(doc.file.path)
        if text.strip():
            RAGService.add_document_to_index(doc.pk, text, location_id=doc.location_id)
            doc.is_processed = True
            doc.save(update_fields=['is_processed'])
            return f"Document {doc.title} indexed"
        return "No text extracted"
    except Exception as e:
        AIErrorLog.objects.create(
            error_type="RAG_TASK_ERROR",
            message=f"Doc PK {doc_pk}: {str(e)}"
        )
        return "Failed"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_telegram_result_task(self, result_pk, report_type='full', delivery_method='auto_telegram',
                              delivered_by_id=None):
    import telebot
    from .models import TestResult, AppConfig, ReportDelivery
    from .services import PDFService

    try:
        result = TestResult.objects.get(pk=result_pk)
        result.refresh_from_db()

        user = result.user
        if not hasattr(user, 'telegram_chat_id') or not user.telegram_chat_id:
            return "User has no telegram_chat_id linked"

        config = AppConfig.load()
        if not config.telegram_bot_token:
            return "No Telegram bot token configured"

        bot = telebot.TeleBot(config.telegram_bot_token)

        from django.core.cache import cache
        from telebot import types

        is_adult = result.child_age >= 18
        person_label = "Участник" if is_adult else "Ребёнок"

        if report_type == 'full':
            if not result.extended_interpretation:
                return "Full report text not ready yet"

            profile_val = result.thinking_profile if result.thinking_profile else "Надо обсудить"
            message_text = (
                f"✅ <b>Полный результат готов!</b>\n\n"
                f"👤 <b>{person_label}:</b> {result.child_name} ({result.child_age} лет)\n"
                f"🧠 <b>Профиль:</b> {profile_val}\n\n"
                f"Подробный отчет во вложенном файле 👇"
            )
            caption_text = "Полный отчет (PDF)"

            # Редактируем CTA-сообщение — убираем кнопки оплаты, показываем статус
            cta_msg_id = cache.get(f"tg_cta_msg_{result.pk}")
            if cta_msg_id:
                try:
                    bot.edit_message_text(
                        "✅ <b>Оплата получена!</b>\nПолный отчёт отправляю следом 👇",
                        chat_id=user.telegram_chat_id,
                        message_id=cta_msg_id,
                        parse_mode='HTML'
                    )
                    cache.delete(f"tg_cta_msg_{result.pk}")
                except Exception:
                    pass  # Сообщение могло быть уже удалено — не критично

            # Удаляем сообщение со ссылкой на оплату (если пользователь нажимал кнопку "Оплатить" в боте)
            pay_msg_id = cache.get(f"tg_pay_msg_{result.pk}")
            if pay_msg_id:
                try:
                    bot.delete_message(
                        chat_id=user.telegram_chat_id,
                        message_id=pay_msg_id
                    )
                    cache.delete(f"tg_pay_msg_{result.pk}")
                except Exception:
                    pass

        else:
            preview_text = (
                f"⚡ <b>Предварительный результат!</b>\n\n"
                f"👤 <b>{person_label}:</b> {result.child_name} ({result.child_age} лет)\n\n"
                f"Предварительная версия файла 👇"
            )
            caption_text = "Предварительный отчет (PDF)"
            message_text = preview_text

        pdf_buffer = PDFService.generate_pdf(result, report_type=report_type)

        safe_name = str(result.child_name).replace(" ", "_")
        prefix = "Short" if report_type == 'short' else "Full"
        file_name = f"{prefix}_Result_{safe_name}.pdf"

        bot.send_message(user.telegram_chat_id, message_text, parse_mode='HTML',
                         disable_web_page_preview=True)

        bot.send_document(
            user.telegram_chat_id,
            pdf_buffer,
            visible_file_name=file_name,
            caption=caption_text
        )

        # Для краткого отчета — отдельное CTA-сообщение с кнопками оплаты
        # Перечитываем из БД свежий статус оплаты (пользователь мог оплатить с сайта пока задача ждала в очереди)
        result.refresh_from_db()
        if report_type == 'short' and config.is_payment_enabled and not result.is_paid:
            price = config.payment_price

            domain = "https://humanprofi.ru"
            if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
                domain = f"https://{settings.ALLOWED_HOSTS[0]}"

            example_url = f"{domain}/static/example_full.pdf"
            if result.child_gender == 'male' and result.suite.example_pdf_male:
                example_url = f"{domain}{result.suite.example_pdf_male.url}"
            elif result.child_gender == 'female' and result.suite.example_pdf_female:
                example_url = f"{domain}{result.suite.example_pdf_female.url}"
            elif config.example_full_report:
                example_url = f"{domain}{config.example_full_report.url}"

            cta_text = (
                f"🎓 <b>Вы можете получить полный отчёт, который содержит:</b>\n"
                f"- Детализированный разбор профиля\n"
                f"- Персональные рекомендации по профессиям (направлениям) с подробным описанием\n"
                f"- Глубокий анализ сильных и слабых сторон\n"
                f"- План развития на ближайшие месяцы\n\n"
                f"🔒 Чтобы получить полный отчет, необходимо произвести оплату.\n"
                f"Стоимость: <b>{price} ₽</b>"
            )

            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(
                text=f"💳 Оплатить полный отчёт за {price} ₽",
                callback_data=f"buy_report_{result.pk}"
            ))
            markup.row(types.InlineKeyboardButton(
                text="📄 Посмотреть пример полного отчета",
                url=example_url
            ))

            sent = bot.send_message(user.telegram_chat_id, cta_text, parse_mode='HTML', reply_markup=markup)
            # Сохраняем message_id, чтобы потом отредактировать при оплате
            cache.set(f"tg_cta_msg_{result.pk}", sent.message_id, timeout=86400 * 7)

        ReportDelivery.objects.create(
            result=result,
            report_type=report_type,
            method=delivery_method,
            delivered_by_id=delivered_by_id
        )

        return f"Sent Telegram report ({report_type}) for result {result_pk}"

    except Exception as e:
        res_obj = TestResult.objects.filter(pk=result_pk).first()
        AIErrorLog.objects.create(
            result=res_obj,
            error_type="TELEGRAM_SEND_TASK_ERROR",
            message=f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        )
        raise e


@shared_task
def notify_payment_confirmed_task(result_pk):
    """Немедленное уведомление в Telegram об успешной оплате (до готовности PDF).
    Редактирует CTA-сообщение, убирая кнопки оплаты. Удаляет платёжное сообщение."""
    import telebot
    from django.core.cache import cache
    from .models import TestResult, AppConfig

    try:
        result = TestResult.objects.get(pk=result_pk)
        user = result.user
        if not user.telegram_chat_id:
            return "No telegram_chat_id"

        config = AppConfig.load()
        if not config.telegram_bot_token:
            return "No bot token"

        bot = telebot.TeleBot(config.telegram_bot_token)

        # Редактируем CTA-сообщение только если PDF ещё не готов
        result.refresh_from_db()
        if not result.extended_interpretation:
            cta_msg_id = cache.get(f"tg_cta_msg_{result.pk}")
            if cta_msg_id:
                try:
                    bot.edit_message_text(
                        "✅ <b>Оплата получена!</b>\n\n"
                        "Полный отчёт формируется, обычно это занимает 1–3 минуты ⏳\n"
                        "Как только будет готов — пришлю сюда автоматически.",
                        chat_id=user.telegram_chat_id,
                        message_id=cta_msg_id,
                        parse_mode='HTML'
                    )
                    # Ключ не удаляем — send_telegram_result_task обновит сообщение при отправке PDF
                except Exception:
                    pass

        # Удаляем сообщение со ссылкой на оплату (если пользователь нажимал кнопку в боте)
        pay_msg_id = cache.get(f"tg_pay_msg_{result.pk}")
        if pay_msg_id:
            # Чистим кеш сразу — сообщение может быть уже удалено другим путём
            cache.delete(f"tg_pay_msg_{result.pk}")
            try:
                bot.delete_message(chat_id=user.telegram_chat_id, message_id=pay_msg_id)
            except Exception:
                pass

        return f"Payment confirmed notification sent for result {result_pk}"

    except Exception as e:
        return f"Error in notify_payment_confirmed_task: {e}"


@shared_task
def notify_ai_error_task(result_pk, report_type='short'):
    """Уведомление пользователя в Telegram об ошибке генерации AI-отчёта."""
    import telebot
    from .models import TestResult, AppConfig

    try:
        result = TestResult.objects.get(pk=result_pk)
        user = result.user
        if not user.telegram_chat_id:
            return "No telegram_chat_id"

        config = AppConfig.load()
        if not config.telegram_bot_token:
            return "No bot token"

        bot = telebot.TeleBot(config.telegram_bot_token)

        if report_type == 'short':
            text = (
                f"⚠️ <b>Возникла техническая проблема</b>\n\n"
                f"При формировании отчёта для <b>{result.child_name}</b> произошла ошибка.\n\n"
                "Мы уже в курсе и разбираемся. Попробуйте зайти на сайт через несколько минут "
                "или обратитесь к нам — поможем вручную."
            )
        else:
            text = (
                f"⚠️ <b>Ошибка генерации полного отчёта</b>\n\n"
                f"Полный отчёт для <b>{result.child_name}</b> не удалось сформировать.\n\n"
                "Мы уже в курсе. Обратитесь к нам — и мы пришлём отчёт вручную."
            )

        bot.send_message(user.telegram_chat_id, text, parse_mode='HTML')
        return f"AI error notification sent for result {result_pk}, type={report_type}"

    except Exception as e:
        return f"Error in notify_ai_error_task: {e}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=20, max_retries=3)
def generate_ai_profile_task(self, result_pk, is_initial=False):
    try:
        result = TestResult.objects.get(pk=result_pk)

        if result.answers_data:
            new_indices = CoreService.calculate_test_indices(result.answers_data, result.suite)
            result.calculated_indices = new_indices

            rel_level, rel_notes = CoreService.calculate_reliability(result.answers_data, result.suite)
            result.reliability_level = rel_level
            result.reliability_notes = rel_notes

            result.save(update_fields=['calculated_indices', 'reliability_level', 'reliability_notes'])

        profile = CoreService.get_ai_profile(result)
        result.thinking_profile = profile
        result.save(update_fields=['thinking_profile'])

        if is_initial:
            generate_short_report_task.delay(result.pk, automatic_send=True)
            generate_extended_report_task.delay(result.pk)

        return f"Profile for {result.child_name}: {profile}"
    except Exception as e:
        res_obj = TestResult.objects.filter(pk=result_pk).first()
        AIErrorLog.objects.create(
            result=res_obj,
            error_type="PROFILE_GEN_ERROR",
            message=f"{str(e)}\n{traceback.format_exc()}"
        )
        raise e


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=15, max_retries=3)
def generate_manager_info_task(self, result_pk):
    try:
        result = TestResult.objects.get(pk=result_pk)
        if result.suite.manager_prompt:
            ai_text = CoreService.get_manager_ai_response(result_obj=result)
            if ai_text:
                result.manager_info = ai_text
                result.save(update_fields=['manager_info'])
        return f"Manager info for {result.child_name} SUCCESS"
    except Exception as e:
        res_obj = TestResult.objects.filter(pk=result_pk).first()
        AIErrorLog.objects.create(
            result=res_obj,
            error_type="MANAGER_TASK_ERROR",
            message=f"{str(e)}\n{traceback.format_exc()}"
        )
        raise e

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=15, max_retries=3)
def notify_manager_new_test_task(self, result_pk):
    try:
        result = TestResult.objects.get(pk=result_pk)
        CoreService.notify_new_test_event(result)
        return f"Notification for result {result_pk} sent"
    except Exception as e:
        print(f"Notification error: {e}")
        return "Notification Failed"


@shared_task(bind=True, max_retries=1)
def check_pending_payments_task(self):
    from django.utils import timezone
    from datetime import timedelta

    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)

    pending_payments = Payment.objects.filter(
        status='pending',
        created_at__lte=five_minutes_ago
    ).select_related('result', 'result__user')

    checked = 0
    approved = 0
    expired = 0

    for payment in pending_payments:
        if payment.created_at <= thirty_minutes_ago:
            payment.status = 'expired'
            payment.save(update_fields=['status'])
            expired += 1
            continue

        result = TochkaPaymentService.check_payment_status(payment)
        checked += 1
        if result:
            approved += 1

    return f"Checked: {checked}, Approved: {approved}, Expired: {expired}"