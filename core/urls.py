from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.conf import settings
from testing.views import (
    auth_view, password_view, reset_password_view,
    test_flow_view, dashboard_view, logout_view, consent_text_view,
    save_answer_ajax, toggle_consent_view, test_landing_view,
    check_phone_ajax, save_contact_request,
    magic_login_view, tg_reset_view, check_result_readiness, check_payment_readiness,
    initiate_payment_view, payment_success_view, payment_failed_view,
    tochka_webhook_view, profile_update_view,
    privacy_view, privacy_bot_view, oferta_view, offer_view,
    view_pdf_inline, check_promo_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', auth_view, name='login'),
    path('check-phone/', check_phone_ajax, name='check_phone_ajax'),
    path('consent/', consent_text_view, name='consent'),
    path('password/', password_view, name='password_enter'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('profile/', profile_update_view, name='profile_update'),
    path('dashboard/<int:pk>/', dashboard_view, name='dashboard_pk'),
    path('logout/', logout_view, name='logout'),
    path('start/', test_flow_view, name='test_start'),
    path('result/<int:pk>/', dashboard_view, name='result'),
    path('result/<int:pk>/check/', check_result_readiness, name='check_result_readiness'),
    path('result/<int:pk>/pay-check/', check_payment_readiness, name='check_payment_readiness'),
    path('save-answer/', save_answer_ajax, name='save_answer_ajax'),
    path('save-contact/', save_contact_request, name='save_contact_request'),
    path('toggle-consent/', toggle_consent_view, name='toggle_consent'),
    path('test/', test_landing_view, name='test_landing'),
    path('magic-login/<str:token>/', magic_login_view, name='magic_login'),
    path('tg-reset/<str:token>/', tg_reset_view, name='tg_reset'),
    path('promo/check/', check_promo_view, name='check_promo'),
    path('pay/<int:pk>/', initiate_payment_view, name='initiate_payment'),
    path('pay/success/', payment_success_view, name='payment_success'),
    path('pay/fail/', payment_failed_view, name='payment_failed'),
    path('webhook/tochka/', tochka_webhook_view, name='tochka_webhook'),
    path('privacy.html', privacy_view, name='privacy'),
    path('privacy_bot.html', privacy_bot_view, name='privacy_bot'),
    path('oferta.html', oferta_view, name='oferta'),
    path('offer.html', offer_view, name='offer'),
    re_path(r'^pdf/(?P<filepath>examples/.+)$', view_pdf_inline, name='view_pdf_inline'),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]