import os
import django
import random
from django.utils import timezone

# Настройка окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')  # Проверьте, что core.settings верно
django.setup()

from users.models import User
from testing.models import TestSuite, TestResult, Question
from testing.services import CoreService


def run():
    print("🚀 Начинаем генерацию тестовых данных для V2...")

    # 1. Получаем тест V2 (ID=5)
    try:
        suite = TestSuite.objects.get(pk=5)
    except TestSuite.DoesNotExist:
        print("❌ Тест с ID=5 не найден!")
        return

    # 2. Получаем или создаем технического юзера
    user, _ = User.objects.get_or_create(phone='+79990000000', defaults={'first_name': 'TEST_BOT'})

    # 3. Сценарии (Матрица ответов для проверки всех профилей)
    # Номера вопросов (q_id), где нужно ставить 5 баллов. Остальные будут 1-2.
    # Основано на вашей формуле V2.
    scenarios = [
        {"name": "TEST_STRATEG", "focus": [1, 13, 16, 6, 7, 4]},  # Аналитик + Лидер
        {"name": "TEST_ENGINEER", "focus": [1, 13, 16, 5, 16, 20]},  # Аналитик + Практик
        {"name": "TEST_PIONEER", "focus": [2, 3, 12, 6, 7, 4]},  # Инноватор + Лидер
        {"name": "TEST_RESEARCHER", "focus": [14, 1, 13, 16]},  # Исследователь + Аналитик
        {"name": "TEST_CONSTRUCTOR", "focus": [15, 2, 11, 12, 5, 20]},  # Творец + Практик
        {"name": "TEST_MEDIATOR", "focus": [8, 9, 10, 11, 19]},  # Коммуникатор + Социальщик
        {"name": "TEST_PRODUCER", "focus": [15, 2, 11, 6, 7]},  # Творец + Лидер
        {"name": "TEST_EXPERT_LOGIC", "focus": [1, 13, 16]},  # Только Аналитик (Эксперт)
        {"name": "TEST_RANDOM_1", "focus": []},  # Полный рандом
        {"name": "TEST_RANDOM_2", "focus": []},
    ]

    questions = Question.objects.filter(suite=suite).order_by('order')

    for scenario in scenarios:
        answers = []
        answers_dict_for_db = []

        print(f"Generating: {scenario['name']}...")

        # Генерация ответов
        for idx, q in enumerate(questions):
            q_num = idx + 1  # Порядковый номер вопроса (1-30)

            # Если это целевой вопрос для профиля - ставим 5, иначе 1 или 2
            if q_num in scenario['focus']:
                score = 5
            elif not scenario['focus']:  # Если рандом
                score = random.randint(1, 5)
            else:
                score = random.randint(1, 2)

            # Формируем структуру как с фронтенда
            answers.append({'question': q.text, 'score': str(score)})
            answers_dict_for_db.append({'question': q.text, 'score': str(score)})

        # 4. САМОЕ ВАЖНОЕ: Расчет через ваш сервис
        # Считаем индексы
        indices = CoreService.calculate_test_indices(answers, suite)

        # Определяем профиль (без AI, чистая математика)
        profile = CoreService.get_thinking_profile(indices, suite)

        # Считаем достоверность
        rel_level, rel_notes = CoreService.calculate_reliability(answers, suite)

        # 5. Сохраняем в БД
        TestResult.objects.create(
            user=user,
            suite=suite,
            child_name=scenario['name'],
            child_gender='male',
            child_age=14,
            answers_data=answers_dict_for_db,
            calculated_indices=indices,
            thinking_profile=profile,  # Записываем определенный профиль
            reliability_level=rel_level,
            reliability_notes=rel_notes,
            created_at=timezone.now(),
            # Имитируем, что AI уже отработал, чтобы не тратить токены:
            short_interpretation="<p>Авто-тест пройден успешно.</p>",
            extended_interpretation="<p>Это техническая запись для проверки логики.</p>"
        )

    print(f"✅ Готово! Создано {len(scenarios)} тестовых записей.")
    print("Теперь зайдите в админку -> Результаты тестирования -> Выделите эти записи -> Действие 'Выгрузить в Excel'")


if __name__ == '__main__':
    run()