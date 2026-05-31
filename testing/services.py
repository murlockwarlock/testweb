import re
import requests
import json
import markdown
import jwt
import logging
from django.urls import reverse
from urllib.parse import quote
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from .models import AppConfig, AIErrorLog

logger = logging.getLogger('testing.payment')


class CoreService:
    @staticmethod
    def send_sms(phone, message, result_obj=None):
        return False

    @staticmethod
    def send_telegram_message(chat_id, message, media_paths=None, media_ids=None, button_text=None, button_url=None,
                              preview_url=None, buttons=None):
        import telebot
        from telebot import types

        config = AppConfig.load()
        if not config.telegram_bot_token:
            return False, "Токен бота не настроен"

        bot = telebot.TeleBot(config.telegram_bot_token)
        markup = None

        if buttons and isinstance(buttons, list):
            markup = types.InlineKeyboardMarkup()
            for row in buttons:
                btns = []
                for btn in row:
                    if btn.get('text') and btn.get('url'):
                        btns.append(types.InlineKeyboardButton(text=btn['text'], url=btn['url']))
                if btns:
                    markup.row(*btns)
        elif button_text and button_url:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text=button_text, url=button_url))

        try:
            if media_ids:
                if len(media_ids) == 1:
                    media_item = media_ids[0]
                    m_type = media_item.get('type')
                    f_id = media_item.get('id')
                    if m_type == 'photo':
                        bot.send_photo(chat_id, f_id, caption=message, parse_mode='HTML', reply_markup=markup)
                    elif m_type == 'video':
                        bot.send_video(chat_id, f_id, caption=message, parse_mode='HTML', reply_markup=markup)
                    elif m_type == 'document':
                        bot.send_document(chat_id, f_id, caption=message, parse_mode='HTML', reply_markup=markup)
                else:
                    media_group = []
                    for index, item in enumerate(media_ids):
                        caption = message if index == 0 else None
                        if item['type'] == 'photo':
                            media_group.append(types.InputMediaPhoto(item['id'], caption=caption, parse_mode='HTML'))
                        elif item['type'] == 'video':
                            media_group.append(types.InputMediaVideo(item['id'], caption=caption, parse_mode='HTML'))
                    bot.send_media_group(chat_id, media_group)
                    if markup:
                        bot.send_message(chat_id, "⬇️", reply_markup=markup)
                return True, "OK"

            elif media_paths:
                sent_msg = None
                if len(media_paths) == 1:
                    file_path = media_paths[0]
                    ext = file_path.split('.')[-1].lower()
                    with open(file_path, 'rb') as f:
                        if ext in ['jpg', 'jpeg', 'png', 'webp']:
                            sent_msg = bot.send_photo(chat_id, f, caption=message, parse_mode='HTML',
                                                      reply_markup=markup)
                        elif ext in ['mp4', 'mov', 'avi']:
                            sent_msg = bot.send_video(chat_id, f, caption=message, parse_mode='HTML',
                                                      reply_markup=markup)
                        else:
                            sent_msg = bot.send_document(chat_id, f, caption=message, parse_mode='HTML',
                                                         reply_markup=markup)
                else:
                    media_group = []
                    for index, path in enumerate(media_paths):
                        ext = path.split('.')[-1].lower()
                        caption = message if index == 0 else None
                        with open(path, 'rb') as f:
                            if ext in ['jpg', 'jpeg', 'png', 'webp']:
                                media_group.append(types.InputMediaPhoto(f.read(), caption=caption, parse_mode='HTML'))
                            elif ext in ['mp4', 'mov', 'avi']:
                                media_group.append(types.InputMediaVideo(f.read(), caption=caption, parse_mode='HTML'))
                    sent_msg = bot.send_media_group(chat_id, media_group)
                    if markup:
                        bot.send_message(chat_id, "⬇️", reply_markup=markup)
                return True, sent_msg

            else:
                if preview_url:
                    text_with_link = f'<a href="{preview_url}">&#8203;</a>{message}'
                    bot.send_message(chat_id, text_with_link, parse_mode='HTML', reply_markup=markup)
                else:
                    bot.send_message(chat_id, message, parse_mode='HTML', reply_markup=markup,
                                     disable_web_page_preview=True)
            return True, "OK"

        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:
                return False, "BLOCKED"
            raise e
        except Exception as e:
            raise e

    @staticmethod
    def notify_admins(message, button_text=None, button_url=None):
        import telebot
        from telebot import types
        config = AppConfig.load()
        if not config.telegram_bot_token or not config.admin_notification_ids:
            return
        bot = telebot.TeleBot(config.telegram_bot_token)

        markup = None
        if button_text and button_url:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text=button_text, url=button_url))

        admin_ids = [x.strip() for x in config.admin_notification_ids.split(',') if x.strip()]
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, f"🔔 <b>Уведомление системы</b>\n\n{message}", parse_mode='HTML',
                                 reply_markup=markup)
            except Exception:
                continue

    @staticmethod
    def get_ai_response(result_obj, is_extended=False):
        from django.core.cache import cache
        cache.clear()
        result_obj.refresh_from_db()

        config = AppConfig.load()
        suite = result_obj.suite
        prompt_template = suite.extended_result_prompt if is_extended else suite.short_result_prompt

        if not prompt_template:
            return "Ошибка: Промпт не задан."

        context_dict, system_content_string = CoreService._build_ai_context(result_obj, suite)
        system_content = f"{suite.report_system_prompt} ДАННЫЕ ТЕСТА: {system_content_string}"

        replacements = {
            "{{child_name}}": context_dict["child_name"],
            "{{child_age}}": context_dict["child_age"],
            "{{child_gender}}": context_dict["child_gender"],
            "{{indices}}": context_dict["indices"],
            "{{profile}}": context_dict["profile"],
            "{{extra_data}}": context_dict["extra_data"],
            "{{reliability}}": context_dict["reliability"],
            "{{answers_data}}": context_dict["answers_data"],
            "{{rag_context}}": context_dict["rag_context"],
            "{{school}}": context_dict["school"],
            "{{grade}}": context_dict["grade"],
            "{{parent_name}}": context_dict["parent_name"],
            "{{parent_phone}}": context_dict["parent_phone"],
            "{{project_name}}": context_dict["project_name"],
            "{{website}}": context_dict["website"],
            "{{support_email}}": context_dict["support_email"],
            "{{test_date}}": context_dict["test_date"],
            "{{test_version}}": context_dict["test_version"],
        }

        def apply_replacements(text):
            if not text: return ""
            res = text
            for tag, val in replacements.items():
                res = res.replace(tag, val).replace(tag.replace("{{", "{{ "), val)
            return res

        max_tokens = config.ai_max_tokens_reasoner if 'reasoner' in suite.ai_model_report else config.ai_max_tokens_chat

        payload = {
            "model": suite.ai_model_report,
            "temperature": suite.ai_temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": apply_replacements(prompt_template)}
            ]
        }

        headers = {"Authorization": f"Bearer {config.deepseek_api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload,
                                     timeout=600)
            response.raise_for_status()
            raw_text = response.json()['choices'][0]['message']['content']
            html = markdown.markdown(apply_replacements(raw_text), extensions=['extra', 'nl2br'])
            # Превращаем голые URL в кликабельные ссылки (не трогаем уже обёрнутые в <a>)
            html = re.sub(
                r'(?<!["\'=>])(https?://[^\s<>"\']+)',
                r'<a href="\1">\1</a>',
                html
            )
            return html
        except Exception as e:
            AIErrorLog.objects.create(
                result=result_obj,
                error_type="REPORT_API_ERROR",
                message=str(e),
                model_used=suite.ai_model_report,
                temp_used=suite.ai_temperature
            )
            raise e

    @staticmethod
    def _build_ai_context(result_obj, suite):
        config = AppConfig.load()
        gender_display = "Мужской" if result_obj.child_gender == 'male' else "Женский"

        if result_obj.calculated_indices:
            filtered_indices = [
                f"{k}: {v}%"
                for k, v in result_obj.calculated_indices.items()
                if k != "Автономность"
            ]
            indices_str = ", ".join(filtered_indices) if filtered_indices else "Нет данных"
        else:
            indices_str = "Нет данных"

        extra_info = "; ".join(
            [f"{k}: {v}" for k, v in result_obj.extra_stats.items() if v]) if result_obj.extra_stats else "Нет данных"
        ans_str = "; ".join([f"Вопрос: {a['question']} - Балл: {a['score']}" for a in
                             result_obj.answers_data]) if result_obj.answers_data else "Нет данных"

        sphere_map = {11: "СОЦИАЛЬНАЯ", 12: "ТЕХНИЧЕСКАЯ", 13: "АНАЛИТИЧЕСКАЯ", 14: "ЕСТЕСТВЕННО-НАУЧНАЯ",
                      15: "ТВОРЧЕСКАЯ/ГУМАНИТАРНАЯ"}
        block_b_scores = []
        if result_obj.answers_data:
            for i, item in enumerate(result_obj.answers_data):
                q_idx = i + 1
                if q_idx in sphere_map:
                    block_b_scores.append({"name": sphere_map[q_idx], "score": int(item.get('score', 0))})

        leading_sphere = max(block_b_scores, key=lambda x: x['score'])['name'] if block_b_scores else "Не определена"

        from .models import ProfileRecommendation
        profile_val = result_obj.thinking_profile or "Не определен"
        rec = ProfileRecommendation.objects.filter(suite=suite, profile_name__iexact=profile_val).first()
        db_rec_text = ""
        if rec:
            db_rec_text = (
                f"ДАННЫЕ ИЗ БАЗЫ ДЛЯ ОТЧЕТА: Описание: {rec.description}. Вектор развития: {rec.vector_development}. "
                f"Рекомендуемые профессии: {rec.top_professions}. План на 3 месяца: {rec.action_plan}. Зоны внимания: {rec.zones_attention}.")

        location_name = result_obj.location.name if result_obj.location else ""
        location_id = result_obj.location_id if result_obj.location_id else None

        rag_data = ""
        if suite.send_rag_context:
            profile_query = result_obj.thinking_profile or "Не определен"
            rag_query = f"Описание профиля {profile_query}. Сфера интересов {leading_sphere}. План действий и профессии."
            rag_data = RAGService.query_knowledge_base(rag_query, n_results=5, location_id=location_id)

        msk_time = timezone.localtime(result_obj.created_at)
        test_date_str = msk_time.strftime("%d.%m.%Y %H:%M")

        context_data = {
            "child_name": str(result_obj.child_name),
            "child_age": str(result_obj.child_age),
            "child_gender": gender_display,
            "indices": indices_str,
            "profile": profile_val,
            "leading_sphere": leading_sphere,
            "db_recommendations": db_rec_text,
            "extra_data": extra_info,
            "reliability": f"{result_obj.reliability_level}. Заметки: {result_obj.reliability_notes}",
            "answers_data": ans_str,
            "rag_context": rag_data if rag_data else "Данные в базе не найдены",
            "location": location_name,
            "school": str(result_obj.school_number or "Не указана"),
            "grade": str(result_obj.grade or "Не указан"),
            "parent_name": str(result_obj.parent_name or "Не указано"),
            "parent_phone": str(result_obj.parent_phone or result_obj.user.phone),
            "project_name": str(config.support_project_name),
            "website": str(config.support_website or "—"),
            "support_email": str(config.support_email or "—"),
            "test_date": test_date_str,
            "test_version": suite.get_version_display()
        }

        system_parts = []
        if suite.send_child_name: system_parts.append(f"Имя: {context_data['child_name']}.")
        if suite.send_child_info: system_parts.append(
            f"Возраст: {context_data['child_age']}. Пол: {context_data['child_gender']}.")
        if suite.send_location and location_name: system_parts.append(f"Местонахождение: {location_name}.")
        if suite.send_indices: system_parts.append(f"Индексы: {context_data['indices']}.")
        if suite.send_thinking_profile: system_parts.append(f"Профиль: {context_data['profile']}.")
        system_parts.append(f"Ведущая сфера интересов: {context_data['leading_sphere']}.")
        if db_rec_text: system_parts.append(db_rec_text)
        if suite.send_reliability: system_parts.append(f"Достоверность: {context_data['reliability']}.")
        if suite.send_extra_data: system_parts.append(f"Доп. вопросы: {context_data['extra_data']}.")
        if suite.send_answers_data: system_parts.append(f"Все ответы: {context_data['answers_data']}.")
        if suite.send_rag_context and rag_data: system_parts.append(
            f"БАЗА ЗНАНИЙ (ИНСТРУКЦИИ): {context_data['rag_context']}.")
        if suite.send_school_info and suite.version != 'V3':
            if suite.version == 'V0':
                system_parts.append(f"Учеба: Учебное заведение {context_data['school']}, группа {context_data['grade']}.")
            else:
                system_parts.append(f"Учеба: Школа {context_data['school']}, {context_data['grade']} класс.")
        if suite.send_parent_info: system_parts.append(
            f"Родитель: {context_data['parent_name']}, тел: {context_data['parent_phone']}.")
        if suite.send_project_info: system_parts.append(
            f"Проект: {context_data['project_name']} ({context_data['website']}).")
        if suite.send_test_meta: system_parts.append(
            f"Тест пройден (Дата и время МСК): {context_data['test_date']} (Версия: {context_data['test_version']}).")

        return context_data, " ".join(system_parts)

    @staticmethod
    def get_ai_profile(result_obj):
        config = AppConfig.load()
        suite = result_obj.suite
        if not suite.profile_prompt:
            return CoreService.get_thinking_profile(result_obj.calculated_indices, suite)

        dynamic_context = CoreService._build_ai_context(result_obj, suite)
        system_content = f"{suite.profile_system_prompt} ДАННЫЕ ТЕСТА: {dynamic_context}"

        max_tokens = config.ai_max_tokens_reasoner if 'reasoner' in suite.ai_model_profile else config.ai_max_tokens_chat

        payload = {
            "model": suite.ai_model_profile,
            "temperature": suite.ai_temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": suite.profile_prompt}
            ]
        }

        headers = {"Authorization": f"Bearer {config.deepseek_api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload,
                                     timeout=60)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip().replace('"', '').replace('.', '')
        except Exception as e:
            AIErrorLog.objects.create(
                result=result_obj,
                error_type="PROFILE_API_ERROR",
                message=str(e),
                model_used=suite.ai_model_profile,
                temp_used=suite.ai_temperature
            )
            return CoreService.get_thinking_profile(result_obj.calculated_indices, suite)

    @staticmethod
    def get_manager_ai_response(result_obj):
        import re
        config = AppConfig.load()
        suite = result_obj.suite
        prompt_template = suite.manager_prompt

        if not prompt_template:
            return ""

        context_dict, system_content_string = CoreService._build_ai_context(result_obj, suite)

        def clean_html(raw_html):
            if not raw_html: return "Отчет еще не сформирован."
            clean = re.sub(r'<.*?>', ' ', raw_html)
            clean = re.sub(r'\s+', ' ', clean)
            return clean.strip()

        short_report_text = clean_html(result_obj.short_interpretation)
        extended_report_text = clean_html(result_obj.extended_interpretation)

        system_content = f"Ты — помощник менеджера по продажам. Твоя цель — дать краткую выжимку для звонка клиенту. Используй данные теста: {system_content_string}"

        replacements = {
            "{{child_name}}": context_dict["child_name"],
            "{{child_age}}": context_dict["child_age"],
            "{{child_gender}}": context_dict["child_gender"],
            "{{indices}}": context_dict["indices"],
            "{{profile}}": context_dict["profile"],
            "{{extra_data}}": context_dict["extra_data"],
            "{{reliability}}": context_dict["reliability"],
            "{{answers_data}}": context_dict["answers_data"],
            "{{rag_context}}": context_dict["rag_context"],
            "{{school}}": context_dict["school"],
            "{{grade}}": context_dict["grade"],
            "{{parent_name}}": context_dict["parent_name"],
            "{{parent_phone}}": context_dict["parent_phone"],
            "{{project_name}}": context_dict["project_name"],
            "{{website}}": context_dict["website"],
            "{{support_email}}": context_dict["support_email"],
            "{{test_date}}": context_dict["test_date"],
            "{{test_version}}": context_dict["test_version"],
            "{{short_report}}": short_report_text,
            "{{extended_report}}": extended_report_text,
        }

        def apply_replacements(text):
            if not text: return ""
            res = text
            for tag, val in replacements.items():
                res = res.replace(tag, val).replace(tag.replace("{{", "{{ "), val)
            return res

        max_tokens = config.ai_max_tokens_chat

        payload = {
            "model": "deepseek-chat",
            "temperature": 0.5,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": apply_replacements(prompt_template)}
            ]
        }

        headers = {"Authorization": f"Bearer {config.deepseek_api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload,
                                     timeout=60)
            response.raise_for_status()
            raw_text = response.json()['choices'][0]['message']['content']
            return raw_text.strip()
        except Exception as e:
            AIErrorLog.objects.create(
                result=result_obj,
                error_type="MANAGER_INFO_ERROR",
                message=str(e),
                model_used="deepseek-chat"
            )
            return ""

    @staticmethod
    def notify_new_test_event(result_obj):
        import telebot
        from telebot import types
        config = AppConfig.load()
        if not config.telegram_bot_token or not config.admin_notification_ids:
            return

        bot = telebot.TeleBot(config.telegram_bot_token)

        # Получаем базовый домен (можно хардкодом или через settings)
        base_url = "https://humanprofi.ru"
        if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
            base_url = f"https://{settings.ALLOWED_HOSTS[0]}"

        admin_url = f"{base_url}/admin/testing/testresult/{result_obj.pk}/change/"

        if result_obj.suite.version == 'V0':
            school_line = f"🎓 <b>Уч. заведение/Группа:</b> {result_obj.school_number}, {result_obj.grade}\n"
        elif result_obj.suite.version != 'V3':
            school_line = f"🎓 <b>Школа/Класс:</b> {result_obj.school_number}, {result_obj.grade}\n"
        else:
            school_line = ""
        is_adult = result_obj.suite.version == 'V3'
        person_label = "Участник" if is_adult else "Ребенок"
        parent_line = "" if is_adult else f"👪 <b>Родитель:</b> {result_obj.parent_name} ({result_obj.parent_phone or result_obj.user.phone})\n"
        message = (
            f"🆕 <b>Новое прохождение теста!</b>\n\n"
            f"👤 <b>{person_label}:</b> {result_obj.child_name} ({result_obj.child_age})\n"
            f"{school_line}"
            f"{parent_line}"
            f"🧠 <b>Профиль:</b> {result_obj.thinking_profile or 'Определяется...'}"
        )

        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(text="🔎 Открыть в админке", url=admin_url)
        markup.add(btn)

        admin_ids = [x.strip() for x in config.admin_notification_ids.split(',') if x.strip()]
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, message, parse_mode='HTML', reply_markup=markup)
            except Exception:
                continue

    @staticmethod
    def calculate_test_indices(answers, suite):
        import re
        scores = {i + 1: int(a['score']) for i, a in enumerate(answers)}
        results = {}
        categories = suite.categories.all()
        for cat in categories:
            formula = cat.formula

            def parse_formula(match):
                q_num = int(match.group(1))
                return str(scores.get(q_num, 0))

            try:
                processed_formula = re.sub(r'\[q(\d+)\]', parse_formula, formula)
                val = eval(processed_formula, {"__builtins__": None}, {})

                # Автономность оставляем float для точности, остальные округляем
                if cat.name == "Автономность":
                    results[cat.name] = round(float(val), 2)
                else:
                    results[cat.name] = int(round(float(val)))
            except Exception:
                results[cat.name] = 0

        # Логика определения стиля работы
        if "Автономность" in results:
            val = results["Автономность"]

            if val >= 3.5:
                style = "ИНДИВИДУАЛЬНЫЙ"
            elif val <= 1.5:
                style = "КОМАНДНЫЙ"
            else:
                style = "ГИБРИДНЫЙ"

            results["Предпочитаемый стиль работы"] = style

        return results

    @staticmethod
    def calculate_reliability(answers, suite):
        scores = {i + 1: int(a['score']) for i, a in enumerate(answers)}
        indicators = []
        rules = suite.reliability_rules.all()
        penalty_score = 0
        contradictions_count = 0

        for rule in rules:
            is_triggered = False
            try:
                if rule.rule_type == 'monotony':
                    target_scores = []
                    if rule.question_indices:
                        q_indices = [int(x.strip()) for x in rule.question_indices.split(',')]
                        target_scores = [scores.get(idx) for idx in q_indices if idx in scores]
                    else:
                        target_scores = [val for key, val in scores.items() if key <= 20]

                    if target_scores:
                        check_val = 2 if suite.version == 'V1' else 3
                        spam_count = target_scores.count(check_val)
                        if (spam_count / len(target_scores)) >= rule.threshold:
                            is_triggered = True

                elif rule.question_indices:
                    q_indices = [int(x.strip()) for x in rule.question_indices.split(',')]
                    if rule.rule_type == 'inconsistency' and len(q_indices) >= 2:
                        val1 = scores.get(q_indices[0], 0)
                        val2 = scores.get(q_indices[1], 0)
                        if abs(val1 - val2) > rule.threshold:
                            is_triggered = True
                    elif rule.rule_type == 'both_high' and len(q_indices) >= 2:
                        val1 = scores.get(q_indices[0], 0)
                        val2 = scores.get(q_indices[1], 0)
                        if val1 >= rule.threshold and val2 >= rule.threshold:
                            is_triggered = True
                    elif rule.rule_type == 'social_desirability':
                        high_scores_count = sum(1 for idx in q_indices if scores.get(idx, 0) >= 4)
                        if high_scores_count >= rule.threshold:
                            is_triggered = True
                    elif rule.rule_type == 'fixed_answer' and len(q_indices) == 1:
                        if scores.get(q_indices[0]) != rule.threshold:
                            is_triggered = True
            except Exception:
                continue

            if is_triggered:
                indicators.append(rule.error_message)
                if suite.version == 'V1':
                    if rule.severity == 'red':
                        penalty_score += 2
                    else:
                        penalty_score = max(penalty_score, 1)
                else:
                    if rule.rule_type in ['inconsistency', 'both_high']:
                        contradictions_count += 1
                    else:
                        if rule.severity == 'red':
                            penalty_score += 2
                        else:
                            penalty_score += 1

        if suite.version != 'V1' and contradictions_count >= 2:
            penalty_score += 1

        if penalty_score == 0:
            return 'green', "; ".join(indicators)
        elif penalty_score == 1:
            return 'yellow', "; ".join(indicators)
        else:
            return 'red', "; ".join(indicators)

    @staticmethod
    def get_thinking_profile(indices, suite):
        if not indices or not suite:
            return "Не определен"

        sorted_indices = sorted(indices.items(), key=lambda x: x[1], reverse=True)

        top1_name, top1_val = sorted_indices[0]
        top2_name, top2_val = sorted_indices[1] if len(sorted_indices) > 1 else (top1_name, 0)
        top3_name, top3_val = sorted_indices[2] if len(sorted_indices) > 2 else (top2_name, 0)

        min_name, min_val = sorted_indices[-1]


        if top1_val >= 80 and top2_val < 60:
            return f"ЭКСПЕРТ ({top1_name.upper()})"

        if suite.version in ['V2', 'V3']:
            if top3_val >= 55 and (top1_val - top3_val) <= 10:
                return "УНИВЕРСАЛ"

        from .models import ProfileMatrix

        match = ProfileMatrix.objects.filter(
            suite=suite,
            index_1__name__in=[top1_name, top2_name],
            index_2__name__in=[top1_name, top2_name]
        ).first()

        if match:
            return match.profile_name

        mapping = {
            frozenset(["АНАЛИТИК", "ЛИДЕР"]): "СТРАТЕГ",
            frozenset(["АНАЛИТИК", "ПРАКТИК"]): "ИНЖЕНЕР",
            frozenset(["ИННОВАТОР", "ЛИДЕР"]): "ПИОНЕР",
            frozenset(["ИССЛЕДОВАТЕЛЬ", "АНАЛИТИК"]): "ИССЛЕДОВАТЕЛЬ",
            frozenset(["ТВОРЕЦ", "ПРАКТИК"]): "КОНСТРУКТОР",
            frozenset(["КОММУНИКАТОР", "СОЦИАЛЬЩИК"]): "МЕДИАТОР",
            frozenset(["ТВОРЕЦ", "ЛИДЕР"]): "ПРОДЮСЕР",
        }

        pair = frozenset([top1_name.upper(), top2_name.upper()])
        return mapping.get(pair, f"{top1_name.upper()}-{top2_name.upper()}")


class RAGService:
    @staticmethod
    def extract_text(file_path):
        import os
        import pandas as pd
        from pypdf import PdfReader
        from docx import Document

        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        try:
            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            elif ext == ".pdf":
                reader = PdfReader(file_path)
                for page in reader.pages:
                    pt = page.extract_text()
                    if pt: text += pt + "\n"
            elif ext == ".docx":
                doc = Document(file_path)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            elif ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
                text = df.to_string()

            text = text.replace('"', '').replace('\\', '')
            text = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
            return text.strip()
        except Exception:
            return ""

    @staticmethod
    def get_vector_collection():
        import chromadb
        from django.conf import settings
        import os
        persist_path = os.path.join(settings.BASE_DIR, "chroma_db")
        client = chromadb.PersistentClient(path=persist_path)
        return client.get_or_create_collection(name="knowledge_base")

    @staticmethod
    def add_document_to_index(doc_id, text, location_id=None):
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        collection = RAGService.get_vector_collection()
        if not text or not str(text).strip(): return

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        raw_chunks = splitter.split_text(str(text))
        final_chunks = [str(c).strip() for c in raw_chunks if str(c).strip()]
        if not final_chunks: return

        doc_ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(final_chunks))]
        metadatas = [{"doc_id": int(doc_id), "location_id": int(location_id) if location_id else 0}
                     for _ in range(len(final_chunks))]
        try:
            collection.add(ids=doc_ids, documents=final_chunks, metadatas=metadatas)
        except Exception as e:
            AIErrorLog.objects.create(error_type="CHROMA_ADD_ERROR", message=f"Doc ID {doc_id}: {str(e)}")

    @staticmethod
    def query_knowledge_base(query, n_results=5, location_id=None):
        try:
            from .models import KnowledgeBaseDocument
            from django.db.models import Q

            qs = KnowledgeBaseDocument.objects.filter(is_processed=True)
            if location_id:
                qs = qs.filter(Q(location__isnull=True) | Q(location_id=location_id))
            else:
                qs = qs.filter(location__isnull=True)

            allowed_ids = list(qs.values_list('id', flat=True))
            if not allowed_ids:
                return ""

            collection = RAGService.get_vector_collection()
            try:
                results = collection.query(
                    query_texts=[str(query)],
                    n_results=n_results,
                    where={"doc_id": {"$in": allowed_ids}}
                )
            except Exception:
                results = collection.query(
                    query_texts=[str(query)],
                    n_results=1,
                    where={"doc_id": {"$in": allowed_ids}}
                )

            if results and results['documents'] and len(results['documents'][0]) > 0:
                return "\n---\n".join([str(d) for d in results['documents'][0]])
            return ""
        except Exception as e:
            AIErrorLog.objects.create(error_type="RAG_QUERY_ERROR", message=str(e))
            return ""


class PDFService:
    @staticmethod
    def generate_pdf(result_obj, report_type='short'):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        import io

        domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'

        def clean_ai_html(text):
            if not text: return ""
            html_content = markdown.markdown(text)
            html_content = html_content.replace('<table>', '<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">')
            html_content = html_content.replace('<table', '<table style="width:100%; table-layout:fixed;"')
            return html_content

        short_content = clean_ai_html(result_obj.short_interpretation)
        extended_content = clean_ai_html(result_obj.extended_interpretation)

        context = {
            'result': result_obj,
            'short_interpretation_pdf': short_content,
            'extended_interpretation_pdf': extended_content,
            'report_type': report_type,
            'timestamp': timezone.now(),
            'domain': domain,
            'protocol': 'https',
        }

        if settings.DEBUG:
            base_url = str(settings.BASE_DIR)
        else:
            base_url = str(settings.STATIC_ROOT) if settings.STATIC_ROOT else str(settings.BASE_DIR)

        pdf_file = io.BytesIO()
        try:
            html_string = render_to_string('pdf_report.html', context)
            HTML(string=html_string, base_url=base_url).write_pdf(pdf_file, presentational_hints=True)
        except Exception as e:
            AIErrorLog.objects.create(
                result=result_obj,
                error_type="PDF_GENERATION_ERROR",
                message=str(e)
            )
            from reportlab.pdfgen import canvas
            pdf_file = io.BytesIO()
            c = canvas.Canvas(pdf_file)
            c.drawString(100, 750, "Error generating PDF report.")
            c.save()

        pdf_file.seek(0)
        return pdf_file


class TochkaPaymentService:
    BASE_URL = "https://enter.tochka.com/uapi/acquiring/v1.0/payments"

    @staticmethod
    def get_headers(config):
        return {
            "Authorization": f"Bearer {config.tochka_jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @staticmethod
    def create_payment_link(result_obj, amount=None):
        from .models import TestResult, Payment
        from django.utils import timezone
        from datetime import timedelta

        config = AppConfig.load()

        if not config.tochka_jwt_token:
            raise Exception("Не настроен JWT токен Точки")
        if not config.tochka_customer_code:
            raise Exception("Не настроен Customer Code")
        if not config.tochka_merchant_id:
            raise Exception("Не настроен Merchant ID")

        recent_payment = Payment.objects.filter(
            result=result_obj,
            status='pending',
            created_at__gte=timezone.now() - timedelta(minutes=15)
        ).first()

        if recent_payment and recent_payment.payment_url:
            return recent_payment.payment_url

        domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[
            0] != '*' else 'humanprofi.ru'
        protocol = 'https'

        redirect_url = f"{protocol}://{domain}/pay/success/?result_id={result_obj.pk}"
        fail_url = f"{protocol}://{domain}/pay/fail/?result_id={result_obj.pk}"

        actual_amount = float(amount) if amount is not None else float(config.payment_price)

        payload = {
            "Data": {
                "customerCode": config.tochka_customer_code,
                "merchantId": config.tochka_merchant_id,
                "amount": actual_amount,
                "purpose": f"Заказ {result_obj.pk}: Оплата профориентационного отчета",
                "paymentMode": ["sbp", "card"],
                "redirectUrl": redirect_url,
                "failRedirectUrl": fail_url,
                "saveCard": False,
            }
        }

        logger.info(
            "[PAYMENT] create_payment_link: result_id=%s child=%s amount=%s payload=%s",
            result_obj.pk, result_obj.child_name, actual_amount, json.dumps(payload, ensure_ascii=False)
        )

        try:
            response = requests.post(
                TochkaPaymentService.BASE_URL,
                json=payload,
                headers=TochkaPaymentService.get_headers(config),
                timeout=10
            )

            logger.info(
                "[PAYMENT] create_payment_link response: result_id=%s status=%s body=%s",
                result_obj.pk, response.status_code, response.text[:500]
            )

            if response.status_code not in [200, 201]:
                AIErrorLog.objects.create(
                    result=result_obj,
                    error_type="PAYMENT_CREATE_ERROR",
                    message=f"Status: {response.status_code}\nBody: {response.text}"
                )
                raise Exception(f"Ошибка банка: {response.status_code}")

            data = response.json().get('Data', {})
            payment_url = data.get('paymentLink')
            operation_id = data.get('operationId')

            logger.info(
                "[PAYMENT] create_payment_link: result_id=%s operationId=%s paymentLink=%s",
                result_obj.pk, operation_id, payment_url
            )

            if not payment_url:
                raise Exception("Банк не вернул ссылку на оплату")

            result_obj.payment_operation_id = operation_id
            result_obj.save(update_fields=['payment_operation_id'])

            Payment.objects.create(
                result=result_obj,
                operation_id=operation_id,
                amount=actual_amount,
                status='pending',
                payment_url=payment_url
            )

            return payment_url

        except Exception as e:
            logger.error("[PAYMENT] create_payment_link exception: result_id=%s error=%s", result_obj.pk, e)
            AIErrorLog.objects.create(
                result=result_obj,
                error_type="PAYMENT_EXCEPTION",
                message=str(e)
            )
            raise e

    @staticmethod
    def handle_webhook(jwt_payload):
        from .models import TestResult, Payment
        from django.utils import timezone
        TOCHKA_PUBLIC_KEY = {
            "kty": "RSA",
            "e": "AQAB",
            "n": "rwm77av7GIttq-JF1itEgLCGEZW_zz16RlUQVYlLbJtyRSu61fCec_rroP6PxjXU2uLzUOaGaLgAPeUZAJrGuVp9nryKgbZceHckdHDYgJd9TsdJ1MYUsXaOb9joN9vmsCscBx1lwSlFQyNQsHUsrjuDk-opf6RCuazRQ9gkoDCX70HV8WBMFoVm-YWQKJHZEaIQxg_DU4gMFyKRkDGKsYKA0POL-UgWA1qkg6nHY5BOMKaqxbc5ky87muWB5nNk4mfmsckyFv9j1gBiXLKekA_y4UwG2o1pbOLpJS3bP_c95rm4M9ZBmGXqfOQhbjz8z-s9C11i-jmOQ2ByohS-ST3E5sqBzIsxxrxyQDTw--bZNhzpbciyYW4GfkkqyeYoOPd_84jPTBDKQXssvj8ZOj2XboS77tvEO1n1WlwUzh8HPCJod5_fEgSXuozpJtOggXBv0C2ps7yXlDZf-7Jar0UYc_NJEHJF-xShlqd6Q3sVL02PhSCM-ibn9DN9BKmD"
        }

        logger.info("[WEBHOOK] handle_webhook: raw payload start=%s", str(jwt_payload)[:80])

        try:
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
            from cryptography.hazmat.backends import default_backend
            import base64 as _base64

            def _b64_to_int(s):
                s += '=' * (4 - len(s) % 4)
                return int.from_bytes(_base64.urlsafe_b64decode(s), 'big')

            public_key = RSAPublicNumbers(
                _b64_to_int(TOCHKA_PUBLIC_KEY['e']),
                _b64_to_int(TOCHKA_PUBLIC_KEY['n'])
            ).public_key(default_backend())

            decoded = jwt.decode(
                jwt_payload,
                key=public_key,
                algorithms=["RS256"],
                options={"verify_aud": False}
            )

            logger.info("[WEBHOOK] decoded payload: %s", json.dumps(decoded, ensure_ascii=False))

            webhook_type = decoded.get('webhookType')
            status = decoded.get('status')
            operation_id = decoded.get('operationId')
            payment_type = decoded.get('paymentType', 'unknown')

            logger.info(
                "[WEBHOOK] webhookType=%s paymentType=%s status=%s operationId=%s",
                webhook_type, payment_type, status, operation_id
            )

            if webhook_type == 'acquiringInternetPayment' and status == 'APPROVED':
                if operation_id:
                    result = TestResult.objects.filter(payment_operation_id=operation_id).first()

                    logger.info(
                        "[WEBHOOK] operationId=%s result_found=%s already_paid=%s",
                        operation_id, bool(result), result.is_paid if result else None
                    )

                    if result and not result.is_paid:
                        result.is_paid = True
                        result.save(update_fields=['is_paid'])

                        Payment.objects.filter(
                            operation_id=operation_id
                        ).update(status='approved', confirmed_at=timezone.now())

                        logger.info("[WEBHOOK] result_id=%s marked as PAID via %s", result.pk, payment_type)

                        if result.user.telegram_chat_id:
                            from .tasks import send_telegram_result_task, notify_payment_confirmed_task
                            notify_payment_confirmed_task.delay(result.pk)
                            send_telegram_result_task.delay(result.pk, report_type='full', delivery_method='auto_webhook')
                            logger.info("[WEBHOOK] notify + send_telegram_result_task queued for result_id=%s", result.pk)

                        return True
                    elif result and result.is_paid:
                        logger.info("[WEBHOOK] result_id=%s already paid, skipping", result.pk)
                    else:
                        logger.warning("[WEBHOOK] operationId=%s — no TestResult found", operation_id)
                else:
                    logger.warning("[WEBHOOK] APPROVED but no operationId in payload: %s", decoded)
            else:
                logger.info("[WEBHOOK] ignored: webhookType=%s status=%s", webhook_type, status)

            return False

        except Exception as e:
            logger.error("[WEBHOOK] handle_webhook exception: %s", e, exc_info=True)
            return False

    @staticmethod
    def check_payment_status(payment):
        from .models import Payment
        from django.utils import timezone

        config = AppConfig.load()

        if not payment.operation_id:
            return False

        check_url = f"{TochkaPaymentService.BASE_URL}/{payment.operation_id}"

        logger.info(
            "[PAYMENT] check_payment_status: payment_id=%s operation_id=%s url=%s",
            payment.pk, payment.operation_id, check_url
        )

        try:
            response = requests.get(
                check_url,
                headers=TochkaPaymentService.get_headers(config),
                timeout=10
            )

            logger.info(
                "[PAYMENT] check_payment_status response: payment_id=%s http=%s body=%s",
                payment.pk, response.status_code, response.text[:500]
            )

            if response.status_code != 200:
                logger.warning("[PAYMENT] check_payment_status: payment_id=%s non-200 response", payment.pk)
                return False

            data = response.json().get('Data', {})
            operations = data.get('Operation', [])
            status = operations[0].get('status') if operations else None

            logger.info("[PAYMENT] check_payment_status: payment_id=%s bank_status=%s", payment.pk, status)

            if status == 'APPROVED':
                payment.status = 'approved'
                payment.confirmed_at = timezone.now()
                payment.save(update_fields=['status', 'confirmed_at'])

                result = payment.result
                if not result.is_paid:
                    result.is_paid = True
                    result.save(update_fields=['is_paid'])
                    logger.info("[PAYMENT] check_payment_status: result_id=%s marked as PAID (fallback)", result.pk)

                    if result.user.telegram_chat_id:
                        from .tasks import send_telegram_result_task, notify_payment_confirmed_task
                        notify_payment_confirmed_task.delay(result.pk)
                        send_telegram_result_task.delay(result.pk, report_type='full', delivery_method='auto_fallback')
                        logger.info("[PAYMENT] notify + send_telegram_result_task queued for result_id=%s", result.pk)
                else:
                    logger.info("[PAYMENT] check_payment_status: result_id=%s already paid", result.pk)

                return True

            elif status == 'EXPIRED':
                logger.info("[PAYMENT] check_payment_status: payment_id=%s → EXPIRED", payment.pk)
                payment.status = 'expired'
                payment.save(update_fields=['status'])
                return False

            elif status in ('REFUNDED', 'ON-REFUND'):
                logger.info("[PAYMENT] check_payment_status: payment_id=%s → %s", payment.pk, status)
                payment.status = 'failed'
                payment.save(update_fields=['status'])
                return False

            else:
                logger.info("[PAYMENT] check_payment_status: payment_id=%s status=%s — no action", payment.pk, status)

        except Exception as e:
            logger.error("[PAYMENT] check_payment_status exception: payment_id=%s error=%s", payment.pk, e, exc_info=True)

        return False