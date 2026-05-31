import os
import django
import json
import time
from datetime import datetime
from django.core.serializers.json import DjangoJSONEncoder
from celery.result import AsyncResult

# 1. Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from testing.models import TestResult
from testing.tasks import generate_ai_profile_task, generate_short_report_task, generate_extended_report_task
from core.celery import app


def enrich_results():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'ai_analysis_full_{timestamp}.json'

    # Берем последние 10 тестовых записей
    results = TestResult.objects.filter(child_name__startswith='TEST_').order_by('-id')[:10]

    if not results.exists():
        print("❌ Тестовые записи не найдены.")
        return

    task_map = {}

    print(f"🤖 Запуск цепочки ИИ для {results.count()} записей...")

    for r in results:
        # Запускаем главную задачу, которая порождает остальные (Профиль -> Отчеты)
        task = generate_ai_profile_task.delay(r.pk)
        task_map[r.pk] = task.id
        print(f"📝 ID {r.pk}: Задача запущена (Task ID: {task.id})")

    # 2. Ожидание завершения
    print("\n⏳ Ожидаю завершения всех задач (это может занять пару минут)...")
    finished = set()
    while len(finished) < len(task_map):
        for pk, tid in task_map.items():
            if pk in finished: continue

            res = AsyncResult(tid, app=app)
            if res.ready():
                finished.add(pk)
                print(f"✅ ID {pk}: ИИ закончил работу.")

        if len(finished) < len(task_map):
            time.sleep(5)  # Ждем 5 секунд перед следующей проверкой

    # 3. Экспорт полных данных
    print(f"\n📦 Все задачи выполнены. Собираю данные в {filename}...")

    final_data = []
    for r in TestResult.objects.filter(pk__in=task_map.keys()):
        final_data.append({
            "id": r.pk,
            "name": r.child_name,
            "mathematical_indices": r.calculated_indices,
            "ai_determined_profile": r.thinking_profile,
            "reliability": {
                "level": r.reliability_level,
                "notes": r.reliability_notes
            },
            "ai_reports": {
                "short": r.short_interpretation,
                "extended": r.extended_interpretation
            },
            "raw_answers": r.answers_data
        })

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4, cls=DjangoJSONEncoder)

    print(f"✨ Готово! Полный отчет сохранен в: /var/testweb/{filename}")


if __name__ == '__main__':
    enrich_results()