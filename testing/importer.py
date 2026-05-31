import gspread
from .models import TestSuite, Question

def run_import(url, suite_id):
    gc = gspread.service_account(filename='credentials.json')
    sheet = gc.open_by_url(url).get_worksheet(0)
    data = sheet.get_all_records()
    suite = TestSuite.objects.get(pk=suite_id)
    for row in data:
        Question.objects.update_or_create(
            suite=suite,
            text=row['text'],
            defaults={'category': row['category'], 'order': row['order']}
        )