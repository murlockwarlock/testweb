import os
import re
import random
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.core.signing import TimestampSigner, BadSignature
from django.http import HttpResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from users.models import User
from .models import TestSuite, Question, TestResult, LandingPage, UserUtm
from .services import CoreService, TochkaPaymentService
from .forms import PhoneForm, UserInfoForm, ResetPasswordForm, RegistrationForm, ProfileUpdateForm
from django.http import JsonResponse

logger = logging.getLogger('testing.payment')


def auth_view(request):
    from django.core.cache import cache
    if request.user.is_authenticated:
        return redirect('dashboard')

    ip = request.META.get('REMOTE_ADDR')
    block_key = f'login_block_{ip}'
    if cache.get(block_key):
        return render(request, 'auth.html', {'error': 'Слишком много попыток. Попробуйте через 5 минут.'})

    for param in ['utm_source', 'utm_medium', 'utm_campaign']:
        val = request.GET.get(param)
        if val:
            request.session[param] = val

    next_url = request.GET.get('next')
    if next_url:
        request.session['auth_next'] = next_url

    if request.method == 'POST':
        attempts_key = f'login_attempts_{ip}'
        attempts = cache.get(attempts_key, 0)

        phone = request.POST.get('phone', '').strip()
        consent = request.POST.get('consent')

        if not phone:
            return render(request, 'auth.html', {'error': 'Необходимо ввести номер телефона'})

        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10 and digits.startswith('9'):
            phone = f"+7{digits}"
        elif len(digits) == 11 and (digits.startswith('7') or digits.startswith('8')):
            phone = f"+7{digits[1:]}"

        if not re.match(r'^\+79\d{9}$', phone):
            cache.set(attempts_key, attempts + 1, 300)
            if attempts + 1 >= 5:
                cache.set(block_key, True, 300)
            return render(request, 'auth.html', {'error': 'Формат номера: +79XXXXXXXXX'})

        # Для новых пользователей требуем согласие, для зарегистрированных — нет
        user_exists = User.objects.filter(phone=phone).exists()
        if not user_exists and not consent:
            return render(request, 'auth.html', {'error': 'Необходимо дать согласие на обработку данных'})

        request.session['login_phone'] = phone
        request.session['consent_accepted'] = True
        return redirect('password_enter')

    return render(request, 'auth.html')


def password_view(request):
    from django.core.cache import cache
    phone = request.session.get('login_phone')
    if not phone:
        return redirect('login')

    ip = request.META.get('REMOTE_ADDR')
    block_key = f'login_block_{ip}'
    if cache.get(block_key):
        return render(request, 'password_enter.html', {'phone': phone, 'error': 'Доступ временно ограничен.'})

    user = User.objects.filter(phone=phone).first()
    error = None
    auth_next = request.session.get('auth_next')

    if request.method == 'POST':
        attempts_key = f'login_attempts_{ip}'
        attempts = cache.get(attempts_key, 0)

        if user:
            password = request.POST.get('password')
            if user.check_password(password):
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                cache.delete(attempts_key)
                request.session.pop('login_phone', None)
                request.session.pop('auth_next', None)
                if auth_next:
                    return redirect(auth_next)
                return redirect('dashboard')

            error = "Неверный пароль"
            cache.set(attempts_key, attempts + 1, 300)
            if attempts + 1 >= 5:
                cache.set(block_key, True, 300)
        else:
            form = RegistrationForm(request.POST)
            if form.is_valid():
                new_user = User.objects.create_user(
                    phone=phone,
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name']
                )
                new_user.security_question = form.cleaned_data['security_question']
                new_user.security_answer = form.cleaned_data['security_answer'].lower().strip()
                new_user.consent_given = True
                new_user.consent_date = timezone.now()
                new_user.save()

                utm_source = request.session.get('utm_source')
                if utm_source:
                    UserUtm.objects.create(
                        user=new_user,
                        utm_source=utm_source,
                        utm_medium=request.session.get('utm_medium'),
                        utm_campaign=request.session.get('utm_campaign')
                    )

                login(request, new_user, backend='django.contrib.auth.backends.ModelBackend')
                cache.delete(attempts_key)
                request.session.pop('login_phone', None)
                request.session.pop('auth_next', None)
                if auth_next:
                    return redirect(auth_next)
                return redirect('test_landing')
            else:
                return render(request, 'password_enter.html', {'phone': phone, 'reg_form': form, 'is_new': True})

    return render(request, 'password_enter.html', {
        'phone': phone,
        'error': error,
        'is_new': user is None,
        'reg_form': RegistrationForm() if user is None else None
    })


def reset_password_view(request):
    phone = request.session.get('login_phone')
    if not phone:
        print("DEBUG: Сброс отклонен - нет телефона в сессии")
        return redirect('login')

    user = User.objects.filter(phone=phone).first()
    if not user:
        print(f"DEBUG: Сброс отклонен - пользователь {phone} не найден")
        return redirect('password_enter')

    questions_dict = {
        'maiden_name': 'Девичья фамилия матери',
        'first_pet': 'Кличка первого питомца',
        'first_car': 'Марка первой машины',
        'favorite_book': 'Любимая книга детства',
    }
    user_question = questions_dict.get(user.security_question, "Секретный вопрос")

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            input_answer = form.cleaned_data['security_answer'].lower().strip()
            if input_answer == user.security_answer:
                user.set_password(form.cleaned_data['password'])
                user.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if 'login_phone' in request.session:
                    del request.session['login_phone']
                return redirect('dashboard')
            else:
                form.add_error('security_answer', 'Неверный ответ')
    else:
        form = ResetPasswordForm()

    return render(request, 'reset_password.html', {
        'form': form,
        'phone': phone,
        'question_text': user_question
    })


def test_flow_view(request):
    if not request.user.is_authenticated:
        return redirect('/?next=' + request.path)

    if request.method == 'POST':
        if 'select_role' in request.POST:
            role = request.POST.get('role_code')
            if role in ['V0', 'V1', 'V2', 'V3']:
                request.session['selected_role'] = role
                request.session.modified = True
            return redirect('test_start')

        elif 'reset_role' in request.POST:
            request.session.pop('selected_role', None)
            request.session.pop('child_info', None)
            request.session.modified = True
            return redirect('test_start')

        elif 'start_test' in request.POST:
            role = request.session.get('selected_role')
            form = UserInfoForm(request.POST, user_phone=request.user.phone, selected_role=role)

            if form.is_valid():
                request.session.pop('selected_suite_id', None)
                request.session.pop('temp_answers', None)

                data = form.cleaned_data
                from datetime import date
                dob = data['child_dob']
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

                location_id = data['location'].id if data['location'] else None
                child_name = data.get('child_name')

                if role == 'V3' and not child_name:
                    child_name = request.user.first_name or "Пользователь"

                parent_name = data.get('parent_name')
                if role in ['V0', 'V1'] and not parent_name:
                    parent_name = request.user.first_name

                request.session['child_info'] = {
                    'role': role,
                    'child_name': child_name,
                    'child_dob': dob.isoformat(),
                    'gender': data.get('gender', 'male'),
                    'location_id': location_id,
                    'school_number': data.get('school_number', ''),
                    'grade': data.get('grade', ''),
                    'parent_name': parent_name,
                    'parent_phone': data.get('parent_phone', request.user.phone),
                    'age': age
                }
                request.session.modified = True

                if request.user.is_staff:
                    suites = TestSuite.objects.filter(version=role)
                else:
                    suites = TestSuite.objects.filter(version=role, is_active=True, is_admin_only=False)

                if not suites.exists():
                    return render(request, 'test_init.html', {
                        'form': form,
                        'selected_role': role,
                        'error': f'Тесты для этой категории ({role}) пока не активны.'
                    })

                role_age_bounds = {'V0': (3, 7), 'V1': (6, 12), 'V2': (12, 18), 'V3': (17, 150)}
                role_age_labels = {
                    'V0': 'дошкольников (3–7 лет)',
                    'V1': 'школьников (6–12 лет)',
                    'V2': 'подростков (12–18 лет)',
                    'V3': 'взрослых (17+ лет)',
                }
                age_warning = None
                if role in role_age_bounds:
                    min_age, max_age = role_age_bounds[role]
                    if age < min_age or age > max_age:
                        age_warning = (
                            f"Этот тест предназначен для {role_age_labels[role]}, "
                            f"а возраст участника — {age} лет."
                        )

                return render(request, 'test_init.html', {
                    'form': form,
                    'suites': suites,
                    'selected_role': role,
                    'child_info': request.session['child_info'],
                    'age_warning': age_warning,
                })

            return render(request, 'test_init.html', {
                'form': form,
                'selected_role': role
            })

        elif 'select_suite' in request.POST:
            suite_id = request.POST.get('suite_id')
            if request.user.is_staff:
                suite = get_object_or_404(TestSuite, pk=suite_id)
            else:
                suite = get_object_or_404(TestSuite, pk=suite_id, is_active=True)
            if suite.is_admin_only and not request.user.is_staff:
                return redirect('test_start')
            request.session['selected_suite_id'] = suite.pk
            request.session.modified = True
            questions = Question.objects.filter(suite=suite).order_by('order')
            final_questions = suite.final_questions.all().order_by('order')
            temp_answers = request.session.get('temp_answers', {})
            scale_range = "1234" if suite.version in ['V1', 'V0'] else "12345"
            return render(request, 'questions.html', {
                'questions': questions,
                'final_questions': final_questions,
                'child_info': request.session.get('child_info'),
                'temp_answers': temp_answers,
                'scale_range': scale_range,
                'suite': suite
            })

        elif 'submit_answers' in request.POST:
            info = request.session.get('child_info')
            suite_id = request.session.get('selected_suite_id')
            if not info or not suite_id:
                return redirect('test_start')
            suite = get_object_or_404(TestSuite, pk=suite_id)
            questions = Question.objects.filter(suite=suite).order_by('order')
            answers = []
            for q in questions:
                score = request.POST.get(f'q_{q.pk}', 0)
                answers.append({
                    'question': q.text,
                    'category': q.category.name if q.category else '',
                    'score': score
                })
            extra_stats = {}
            for fq in suite.final_questions.all():
                user_answer = request.POST.get(f'final_{fq.pk}', '').strip()
                if user_answer:
                    extra_stats[fq.text] = user_answer
            from .models import Location
            loc_obj = None
            if info.get('location_id'):
                loc_obj = Location.objects.filter(pk=info['location_id']).first()
            indices = CoreService.calculate_test_indices(answers, suite)
            rel_level, rel_notes = CoreService.calculate_reliability(answers, suite)
            result = TestResult.objects.create(
                user=request.user,
                suite=suite,
                child_name=info['child_name'],
                child_gender=info['gender'],
                child_dob=info['child_dob'],
                child_age=info['age'],
                school_number=info['school_number'],
                grade=info['grade'],
                parent_name=info['parent_name'],
                parent_phone=info.get('parent_phone', ''),
                location=loc_obj,
                answers_data=answers,
                extra_stats=extra_stats,
                calculated_indices=indices,
                reliability_level=rel_level,
                reliability_notes=rel_notes,
                manager_info=""
            )
            from .tasks import generate_ai_profile_task, generate_manager_info_task, notify_manager_new_test_task
            generate_ai_profile_task.delay(result.pk, is_initial=True)
            generate_manager_info_task.delay(result.pk)
            notify_manager_new_test_task.delay(result.pk)
            request.session.pop('temp_answers', None)
            request.session.pop('child_info', None)
            request.session.pop('selected_suite_id', None)
            request.session.pop('selected_role', None)
            request.session.modified = True
            return redirect('result', pk=result.pk)

    selected_role = request.session.get('selected_role')
    if selected_role:
        initial_data = request.session.get('child_info', {})
        initial_data['role'] = selected_role
        form = UserInfoForm(initial=initial_data, selected_role=selected_role)
        return render(request, 'test_init.html', {'form': form, 'selected_role': selected_role})
    return render(request, 'test_init.html', {'selected_role': None})


@login_required
def dashboard_view(request, pk=None):
    import struct
    import hmac
    import hashlib
    import base64
    import time
    from django.conf import settings
    from .models import TestResult, AppConfig
    from django.shortcuts import render, get_object_or_404

    user_id = request.user.pk
    timestamp = int(time.time())
    data = struct.pack('>II', user_id, timestamp)

    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        data,
        hashlib.sha256
    ).digest()

    final_bytes = data + signature[:12]
    tg_connect_token = base64.urlsafe_b64encode(final_bytes).decode().rstrip('=')

    config = AppConfig.load()
    bot_name = config.telegram_bot_name if config.telegram_bot_name else "Humanprofibot"

    context_extras = {
        'tg_token': tg_connect_token,
        'telegram_bot_name': bot_name,
        'config': config
    }

    if pk:
        from .models import Payment
        result = get_object_or_404(TestResult, pk=pk, user=request.user)

        if result.short_interpretation:
            result.short_interpretation = f'<div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">{result.short_interpretation}</div>'

        if result.extended_interpretation and result.is_paid:
            result.extended_interpretation = f'<div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">{result.extended_interpretation}</div>'
        else:
            result.extended_interpretation = ""

        has_pending_payment = Payment.objects.filter(result=result, status='pending').exists()
        context_extras['result'] = result
        context_extras['has_pending_payment'] = has_pending_payment
        return render(request, 'test_result.html', context_extras)

    results = TestResult.objects.filter(user=request.user).order_by('-created_at')
    context_extras['results'] = results
    return render(request, 'dashboard.html', context_extras)

def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect('test_landing')


def consent_text_view(request):
    return render(request, 'consent.html')


def privacy_view(request):
    return render(request, 'privacy.html')


def privacy_bot_view(request):
    return render(request, 'privacy_bot.html')


def oferta_view(request):
    return render(request, 'oferta.html')


def offer_view(request):
    return render(request, 'offer.html')


def check_phone_ajax(request):
    phone = request.GET.get('phone', '').strip()
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10 and digits.startswith('9'):
        phone = f"+7{digits}"
    elif len(digits) == 11 and (digits.startswith('7') or digits.startswith('8')):
        phone = f"+7{digits[1:]}"
    exists = User.objects.filter(phone=phone).exists()
    return JsonResponse({'exists': exists})


def save_answer_ajax(request):
    from django.http import JsonResponse
    if request.method == 'POST' and request.user.is_authenticated:
        question_id = request.POST.get('question_id')
        score = request.POST.get('score')

        answers = request.session.get('temp_answers', {})
        answers[question_id] = score
        request.session['temp_answers'] = answers
        request.session.modified = True
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def toggle_consent_view(request):
    from django.utils import timezone
    user = request.user
    user.consent_given = not user.consent_given
    if user.consent_given:
        user.consent_date = timezone.now()
    user.save()
    return redirect('dashboard')


def test_landing_view(request):
    import re
    landing = LandingPage.load()
    for param in ['utm_source', 'utm_medium', 'utm_campaign']:
        val = request.GET.get(param)
        if val:
            request.session[param] = val
    video_id = None
    if landing.video_url:
        regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/|youtube\.com\/live\/)([^"&?\/\s]{11})'
        match = re.search(regex, landing.video_url)
        if match:
            video_id = match.group(1)
    is_in_progress = False
    if request.user.is_authenticated:
        if request.session.get('child_info') or request.session.get('selected_suite_id'):
            is_in_progress = True
    return render(request, 'landing.html', {
        'landing': landing,
        'youtube_id': video_id,
        'is_in_progress': is_in_progress
    })


def error_404_view(request, exception):
    return render(request, '404.html', status=404)

def error_500_view(request):
    return render(request, '500.html', status=500)


def magic_login_view(request, token):
    signer = TimestampSigner()
    try:
        user_id = signer.unsign(token, max_age=300)
        user = User.objects.get(pk=user_id)

        if not user.is_active:
            return redirect('login')

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('dashboard')

    except (BadSignature, User.DoesNotExist):
        return redirect('login')


def tg_reset_view(request, token):
    signer = TimestampSigner()
    try:
        phone = signer.unsign(token, max_age=600)
        request.session['login_phone'] = phone
        return redirect('reset_password')

    except BadSignature:
        return redirect('login')


def save_contact_request(request):
    from django.http import JsonResponse
    from django.conf import settings
    from .models import TestResult
    from .services import CoreService

    if request.method == 'POST' and request.user.is_authenticated:
        result_id = request.POST.get('result_id')
        method = request.POST.get('method')
        value = request.POST.get('value', '').strip()

        if not value:
            return JsonResponse({'status': 'error', 'message': 'Пустое значение'}, status=400)

        if method == 'email':
            if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                return JsonResponse({'status': 'error', 'message': 'Некорректный E-mail'}, status=400)

        elif method == 'max':
            digits_only = re.sub(r'\D', '', value)
            is_phone_like = len(digits_only) > 5

            if is_phone_like:
                if len(digits_only) < 10 or len(digits_only) > 12:
                    return JsonResponse({'status': 'error', 'message': 'Номер телефона должен содержать 10-12 цифр'},
                                        status=400)
            else:
                if len(value) < 3:
                    return JsonResponse({'status': 'error', 'message': 'Никнейм слишком короткий'}, status=400)

        result = get_object_or_404(TestResult, pk=result_id, user=request.user)

        if method in ['email', 'max']:
            result.contact_method = method
            result.contact_detail = value
            result.save()

            domain = 'humanprofi.ru'
            if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
                domain = settings.ALLOWED_HOSTS[0]

            admin_url = f"https://{domain}/admin/testing/testresult/{result.pk}/change/"

            msg = (
                f"📝 <b>Новая заявка на отчет!</b>\n"
                f"Способ: {method.upper()}\n"
                f"Контакт: {value}\n"
                f"Ребенок: {result.child_name}\n"
                f"Родитель: {request.user.first_name} ({request.user.phone})"
            )
            CoreService.notify_admins(msg, button_text="🔎 Открыть в админке", button_url=admin_url)

            return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


def check_result_readiness(request, pk):
    from django.http import JsonResponse
    from .models import TestResult, AIErrorLog

    if not request.user.is_authenticated:
        return JsonResponse({'ready': False, 'error': False})

    try:
        result = TestResult.objects.get(pk=pk, user=request.user)
        is_ready = bool(result.short_interpretation)

        has_error = False
        if not is_ready:
            has_error = AIErrorLog.objects.filter(
                result=result,
                error_type__in=['SHORT_REPORT_TASK_ERROR', 'PROFILE_GEN_ERROR']
            ).exists()

        return JsonResponse({'ready': is_ready, 'error': has_error})
    except TestResult.DoesNotExist:
        return JsonResponse({'ready': False, 'error': False})


@login_required
def check_payment_readiness(request, pk):
    result = get_object_or_404(TestResult, pk=pk, user=request.user)
    return JsonResponse({'paid': result.is_paid})


def error_400_view(request, exception):
    return render(request, '400.html', status=400)


def error_403_view(request, exception):
    return render(request, '403.html', status=403)


def error_404_view(request, exception):
    return render(request, '404.html', status=404)


def error_500_view(request):
    return render(request, '500.html', status=500)


@login_required
def initiate_payment_view(request, pk):
    from .models import AppConfig, PromoCode, Payment
    from django.db.models import F

    result = get_object_or_404(TestResult, pk=pk, user=request.user)

    if result.is_paid:
        return redirect('dashboard_pk', pk=pk)

    config = AppConfig.load()
    promo_error = None
    promo_obj = None
    final_price = config.payment_price
    promo_code_str = ''

    if request.method == 'POST':
        promo_code_str = request.POST.get('promo_code', '').strip().upper()
        action = request.POST.get('action', '')
    else:
        promo_code_str = request.GET.get('promo', '').strip().upper()
        action = ''

    if promo_code_str:
        try:
            promo_obj = PromoCode.objects.get(code=promo_code_str)
            if promo_obj.is_valid():
                final_price = promo_obj.final_price
            else:
                promo_error = "Промокод недействителен, исчерпан или истёк"
                promo_obj = None
        except PromoCode.DoesNotExist:
            promo_error = "Промокод не найден"

    if request.method == 'POST' and action == 'pay':
        if promo_obj and final_price == 0:
            result.is_paid = True
            result.promo_code = promo_obj
            result.save()
            PromoCode.objects.filter(pk=promo_obj.pk).update(used_count=F('used_count') + 1)
            Payment.objects.create(result=result, amount=0, status='approved')
            logger.info("[PROMO] Free promo %s used for result %s by user %s", promo_code_str, pk, request.user.pk)
            return redirect(f'/pay/success/?result_id={pk}')
        else:
            amount = final_price if promo_obj else config.payment_price
            try:
                payment_url = TochkaPaymentService.create_payment_link(result, amount=amount)
                if promo_obj:
                    result.promo_code = promo_obj
                    result.save(update_fields=['promo_code'])
                    PromoCode.objects.filter(pk=promo_obj.pk).update(used_count=F('used_count') + 1)
                return redirect(payment_url)
            except Exception as e:
                return render(request, 'payment_error.html', {'error': str(e), 'pk': pk})

    return render(request, 'payment_page.html', {
        'result': result,
        'config': config,
        'promo_error': promo_error,
        'promo_obj': promo_obj,
        'final_price': final_price,
        'promo_code_str': promo_code_str,
    })


@login_required
def check_promo_view(request):
    from .models import PromoCode, AppConfig

    code = request.GET.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'valid': False, 'message': 'Введите промокод'})

    try:
        promo = PromoCode.objects.get(code=code)
        if promo.is_valid():
            config = AppConfig.load()
            price = promo.final_price
            if promo.discount_type == 'free':
                price_display = 'Бесплатно'
            else:
                price_display = f'{price} ₽'
            return JsonResponse({
                'valid': True,
                'discount_type': promo.discount_type,
                'final_price': price,
                'price_display': price_display,
                'original_price': config.payment_price,
                'message': f'Промокод применён: {price_display}',
            })
        else:
            return JsonResponse({'valid': False, 'message': 'Промокод недействителен, исчерпан или истёк'})
    except PromoCode.DoesNotExist:
        return JsonResponse({'valid': False, 'message': 'Промокод не найден'})


def payment_success_view(request):
    pk = request.GET.get('result_id')
    return render(request, 'payment_success.html', {'pk': pk})


def payment_failed_view(request):
    pk = request.GET.get('result_id')
    return render(request, 'payment_failed.html', {'pk': pk})


@csrf_exempt
def tochka_webhook_view(request):
    import json
    if request.method == 'POST':
        logger.info(
            "[WEBHOOK] incoming POST: content_type=%s content_length=%s",
            request.content_type, request.META.get('CONTENT_LENGTH', '?')
        )
        try:
            try:
                body_data = json.loads(request.body)
                jwt_token = body_data.get('data')
                logger.info("[WEBHOOK] body parsed as JSON, jwt extracted from 'data' field")
            except json.JSONDecodeError:
                jwt_token = None

            if not jwt_token:
                jwt_token = request.body.decode('utf-8')
                logger.info("[WEBHOOK] body used as raw JWT string, length=%s", len(jwt_token))

            success = TochkaPaymentService.handle_webhook(jwt_token)

            if success:
                logger.info("[WEBHOOK] handled successfully → 200 OK")
                return HttpResponse("OK", status=200)
            else:
                logger.info("[WEBHOOK] ignored (no action taken) → 200 Ignored")
                return HttpResponse("Ignored", status=200)

        except Exception as e:
            logger.error("[WEBHOOK] unhandled exception: %s", e, exc_info=True)
            return HttpResponse(f"Error: {str(e)}", status=500)

    logger.warning("[WEBHOOK] non-POST request: method=%s", request.method)
    return HttpResponse("Method not allowed", status=405)


@login_required
def profile_update_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'profile.html', {'form': form})


def view_pdf_inline(request, filepath):
    """Отдаёт PDF из медиа-папки с Content-Disposition: inline (открытие в браузере)."""
    # Безопасность: разрешаем только файлы из папки examples/
    if not filepath.startswith('examples/'):
        raise Http404
    full_path = os.path.realpath(os.path.join(settings.MEDIA_ROOT, filepath))
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    if not full_path.startswith(media_root) or not os.path.isfile(full_path):
        raise Http404
    response = FileResponse(open(full_path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(full_path)}"'
    return response