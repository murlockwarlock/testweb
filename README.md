# ProfTest Web Platform

A comprehensive, Django-based web platform designed for automated psychological and professional testing. The system includes complex test logic, payment integrations, PDF report generation, and an administrative dashboard for deep analytics.

## 🌟 Key Features
- **Dynamic Test Engine:** Create and manage multi-step psychological/professional tests.
- **AI Result Enrichment:** Automated generation of deep, personalized text reports based on test results using AI integrations.
- **Payment Gateway:** Built-in integration with YooKassa/Robokassa for monetizing premium test results.
- **PDF Generation:** Automatically compiles detailed, beautifully formatted PDF reports for users.
- **Admin Analytics:** Custom Django admin dashboards for tracking conversions, payments, and test completion rates.
- **Mailing System:** Built-in campaign manager to send targeted newsletters and follow-ups.

## 💳 Advanced Payment Integration
This project showcases deep expertise in e-commerce and billing systems:
- **YooKassa & Robokassa:** Fully integrated payment gateways for seamless monetization of psychological tests.
- **Automated Billing Logic:** Secure webhook handlers that verify payment signatures, manage order statuses, and automatically grant access to premium test results upon successful payment.
- **Celery Background Tasks:** Scheduled tasks (e.g. `check-pending-payments`) to ensure no transaction is lost even if webhook delivery fails.

## 🚀 Tech Stack
- **Backend:** Django 4+, Python
- **Database:** PostgreSQL (production), SQLite (development)
- **Task Queue:** Celery + Redis
- **Frontend:** HTML5, TailwindCSS, JavaScript

## 🛡️ Security Note
This is a sanitized open-source release. Sensitive keys, production databases (`db.sqlite3`), and API secrets have been removed to protect user data.

## 📄 License
MIT License
