import os
import django
import json
import random
from datetime import datetime
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

# 1. Настройка окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import User
from testing.models import TestSuite, TestResult, Question
from testing.services import CoreService


def run_suite_and_export():
    # Настройки путей и имен
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'analysis_v2_{timestamp}.json'
    base_dir = '/var/testweb/'
    full_path = os.path.join(base_dir, filename)

    print(f"🚀 Запуск комплексного теста V2...")

    # 2. Инициализация данных
    try:
        suite = TestSuite.objects.get(pk=5)
    except TestSuite.DoesNotExist:
        print("❌ Ошибка: Тест с ID=5 не найден в базе!")
        return

    user, _ = User.objects.get_or_create(
        phone='+79990000000',
        defaults={'first_name': 'TEST_BOT', 'is_active': True}
    )

    # Описания сценариев
    scenarios = [
        {"name": "TEST_STRATEG", "focus": [1, 13, 16, 6, 7, 4]},  # Аналитик + Лидер
        {"name": "TEST_ENGINEER", "focus": [1, 13, 16, 5, 16, 20]},  # Аналитик + Практик
        {"name": "TEST_PIONEER", "focus": [2, 3, 12, 6, 7, 4]},  # Инноватор + Лидер
        {"name": "TEST_RESEARCHER", "focus": [14, 1, 13, 16]},  # Исследователь + Аналитик
        {"name": "TEST_CONSTRUCTOR", "focus": [15, 2, 11, 12, 5, 20]},  # Творец + Практик
        {"name": "TEST_MEDIATOR", "focus": [8, 9, 10, 11, 19]},  # Коммуникатор + Социальщик
        {"name": "TEST_PRODUCER", "focus": [15, 2, 11, 6, 7]},  # Творец + Лидер
        {"name": "TEST_EXPERT_LOGIC", "focus": [1, 13, 16]},  # Только Аналитик
        {"name": "TEST_RANDOM_1", "focus": []},
        {"name": "TEST_RANDOM_2", "focus": []},
    ]

    questions = Question.objects.filter(suite=suite).order_by('order')
    created_ids = []

    # 3. Генерация прохождений
    for scenario in scenarios:
        answers_for_service = []
        answers_for_db = []

        for idx, q in enumerate(questions):
            q_num = idx + 1
            if q_num in scenario['focus']:
                score = 5
            elif not scenario['focus']:
                score = random.randint(1, 5)
            else:
                score = random.randint(1, 2)

            ans_item = {'question': q.text, 'score': str(score)}
            answers_for_service.append(ans_item)
            answers_for_db.append(ans_item)

        # Математика сервиса
        indices = CoreService.calculate_test_indices(answers_for_service, suite)
        profile = CoreService.get_thinking_profile(indices, suite)
        rel_level, rel_notes = CoreService.calculate_reliability(answers_for_service, suite)

        # Сохранение
        res = TestResult.objects.create(
            user=user,
            suite=suite,
            child_name=scenario['name'],
            child_gender='male',
            child_age=14,
            answers_data=answers_for_db,
            calculated_indices=indices,
            thinking_profile=profile,
            reliability_level=rel_level,
            reliability_notes=rel_notes,
            short_interpretation="Technical Test",
            extended_interpretation="Technical Test"
        )
        created_ids.append(res.pk)
        print(f"✅ Создан результат: {scenario['name']} (ID: {res.pk}) -> {profile}")

    # 4. Экспорт только созданных данных
    print(f"📦 Экспортирую {len(created_ids)} записей в {filename}...")

    export_data = []
    results_to_export = TestResult.objects.filter(pk__in=created_ids).order_by('id')

    for r in results_to_export:
        export_data.append({
            "id": r.pk,
            "scenario_name": r.child_name,
            "suite_version": r.suite.version,
            "calculated_indices": r.calculated_indices,
            "final_profile": r.thinking_profile,
            "reliability": {
                "level": r.reliability_level,
                "notes": r.reliability_notes
            },
            "raw_answers": [
                {"q": a.get('question'), "score": a.get('score')}
                for a in (r.answers_data or [])
            ]
        })

    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    print(f"✨ Все готово! Файл сохранен: {full_path}")


if __name__ == '__main__':
    run_suite_and_export()