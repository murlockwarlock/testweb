import os
import django
import json
import time
import random
from datetime import datetime
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import User
from testing.models import TestSuite, TestResult, Question
from testing.services import CoreService
from testing.tasks import generate_ai_profile_task


def run_full_cycle():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'full_ai_personalized_report_{timestamp}.json'

    try:
        suite = TestSuite.objects.get(pk=5)
    except TestSuite.DoesNotExist:
        print("❌ Ошибка: Тест V2 (ID 5) не найден.")
        return

    user, _ = User.objects.get_or_create(phone='+79990000000', defaults={'first_name': 'TEST_BOT'})
    questions = Question.objects.filter(suite=suite).order_by('order')

    # Сценарии с добавленными хобби для проверки персонализации
    scenarios = [
        {"name": "TEST_STRATEG", "focus": [1, 13, 16, 6, 7, 4], "hobby": "Шахматы, программирование на Python"},
        {"name": "TEST_ENGINEER", "focus": [1, 13, 16, 5, 16, 20],
         "hobby": "Разборка старых радиоприемников, LEGO Technic"},
        {"name": "TEST_PIONEER", "focus": [2, 3, 12, 6, 7, 4], "hobby": "Ведение блога, создание своего мерча"},
        {"name": "TEST_RESEARCHER", "focus": [14, 1, 13, 16], "hobby": "Астрономия, чтение энциклопедий о космосе"},
        {"name": "TEST_CONSTRUCTOR", "focus": [15, 2, 11, 12, 5, 20], "hobby": "Рисование, создание 3D-моделей зданий"},
        {"name": "TEST_MEDIATOR", "focus": [8, 9, 10, 11, 19],
         "hobby": "Волонтерство в приюте для животных, психология"},
        {"name": "TEST_PRODUCER", "focus": [15, 2, 11, 6, 7], "hobby": "Монтаж видео для TikTok, театральный кружок"},
        {"name": "TEST_EXPERT_LOGIC", "focus": [1, 13, 16], "hobby": "Математические олимпиады, решение головоломок"},
        {"name": "TEST_RANDOM_1", "focus": [], "hobby": "Видеоигры (Minecraft, Roblox)"},
        {"name": "TEST_RANDOM_2", "focus": [], "hobby": "Чтение фэнтези, изучение иностранных языков"},
    ]

    created_ids = []
    print(f"🏁 Запуск полной проверки персонализации (10 сценариев)...")

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

        # Расчет индексов (подхватит любое кол-во шкал из админки)
        indices = CoreService.calculate_test_indices(answers, suite)
        rel_level, rel_notes = CoreService.calculate_reliability(answers, suite)

        # Формируем extra_stats для передачи хобби в ИИ
        extra_stats = {
            "интересы_и_хобби": scenario['hobby'],
            "любимые_предметы": "Математика, Информатика" if "Аналитик" in str(
                scenario['focus']) else "Литература, Искусство"
        }

        res = TestResult.objects.create(
            user=user,
            suite=suite,
            child_name=scenario['name'],
            child_gender='male',
            child_age=14,
            answers_data=answers,
            extra_stats=extra_stats,  # Теперь ИИ увидит эти данные
            calculated_indices=indices,
            reliability_level=rel_level,
            reliability_notes=rel_notes,
            short_interpretation="",
            extended_interpretation=""
        )
        created_ids.append(res.pk)

        generate_ai_profile_task.delay(res.pk)
        print(f"✅ [{scenario['name']}] Запись ID {res.pk} создана. Хобби: {scenario['hobby']}")

    print("\n⏳ Ожидание ответов (с учетом глубокой персонализации)...")

    start_time = time.time()
    while True:
        finished = TestResult.objects.filter(pk__in=created_ids).exclude(extended_interpretation="").exclude(
            extended_interpretation="Technical Test")
        count = finished.count()
        print(f"🔄 Обработано ИИ: {count} из 10...")
        if count == 10 or (time.time() - start_time > 1800): break
        time.sleep(30)

    # Финальный экспорт
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

    with open(f'/var/testweb/{filename}', 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    print(f"\n✨ ПРОВЕРКА ЗАВЕРШЕНА! Файл: /var/testweb/{filename}")


if __name__ == '__main__':
    run_full_cycle()