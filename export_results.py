import os
import django
import json
from django.core.serializers.json import DjangoJSONEncoder

# 1. Настройка окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')  # Убедитесь, что core.settings верно
django.setup()

from testing.models import TestResult


def export_to_json():
    print("📦 Начинаю выгрузку результатов в JSON...")

    # 2. Фильтруем результаты.
    # Берем те, что начинаются на "TEST_" (наши авто-тесты)
    # или, если их нет, берем последние 20 любых результатов.
    results = TestResult.objects.filter(child_name__startswith='TEST_').order_by('-created_at')

    if not results.exists():
        print("⚠️ Тестовые данные (TEST_...) не найдены. Выгружаю последние 10 реальных прохождений.")
        results = TestResult.objects.all().order_by('-id')[:10]

    export_data = []

    for r in results:
        # Собираем только важное для анализа логики
        item = {
            "id": r.pk,
            "scenario_name": r.child_name,  # Имя сценария (например, TEST_STRATEG)
            "suite_version": r.suite.version if r.suite else "N/A",

            # САМОЕ ВАЖНОЕ: Что насчитала математика
            "calculated_indices": r.calculated_indices,

            # ИТОГ: Какой профиль присвоился
            "final_profile": r.thinking_profile,

            # ДОСТОВЕРНОСТЬ: Сработали ли ловушки
            "reliability": {
                "level": r.reliability_level,
                "notes": r.reliability_notes
            },

            # ОТВЕТЫ (Чтобы я мог проверить, если баллы кривые)
            # Упрощаем структуру для читаемости
            "raw_answers": [
                {"q": a.get('question'), "score": a.get('score')}
                for a in (r.answers_data or [])
            ]
        }
        export_data.append(item)

    # 3. Сохраняем в файл
    filename = 'test_results_analysis.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    print(f"✅ Готово! Данные сохранены в файл: {filename}")
    print(f"Всего выгружено записей: {len(export_data)}")


if __name__ == '__main__':
    export_to_json()