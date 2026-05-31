import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Location
from users.models import User

class PhoneForm(forms.Form):
    phone = forms.CharField(max_length=20)
    consent = forms.BooleanField(
        required=True,
        error_messages={'required': 'Вы должны дать согласие на обработку данных для продолжения'}
    )
    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10 and digits.startswith('9'):
            phone = f"+7{digits}"
        elif len(digits) == 11 and (digits.startswith('7') or digits.startswith('8')):
            phone = f"+7{digits[1:]}"
        if not re.match(r'^\+79\d{9}$', phone):
            raise ValidationError("Формат номера должен быть +79XXXXXXXXX")
        return phone


class UserInfoForm(forms.Form):
    GENDER_CHOICES = [('male', 'Мужской'), ('female', 'Женский')]
    role = forms.CharField(widget=forms.HiddenInput, required=False)
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        empty_label="Выберите город/регион",
        required=False,
        widget=forms.Select(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold appearance-none'})
    )
    child_name = forms.CharField(
        max_length=255,
        min_length=2,
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold', 'placeholder': 'Имя и Фамилия'})
    )
    child_dob = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'hidden'}))
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold appearance-none'})
    )
    school_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold'})
    )
    grade = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold'})
    )
    parent_name = forms.CharField(
        max_length=255,
        min_length=2,
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold'})
    )
    parent_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold', 'placeholder': '+79XXXXXXXXX'})
    )

    def __init__(self, *args, **kwargs):
        self.user_phone = kwargs.pop('user_phone', None)
        self.selected_role = kwargs.pop('selected_role', None)
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.all().order_by('order', 'name')

    def clean_child_dob(self):
        dob = self.cleaned_data.get('child_dob')
        if not dob:
            return None
        from datetime import date
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 4 or age > 100:
            raise ValidationError(f"Возраст участника — {age} л. Тестирование доступно от 4 до 100 лет.")
        return dob

    def clean_parent_phone(self):
        phone = self.cleaned_data.get('parent_phone', '').strip()
        if not phone:
            return phone
        import re
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10 and digits.startswith('9'):
            phone = f"+7{digits}"
        elif len(digits) == 11 and (digits.startswith('7') or digits.startswith('8')):
            phone = f"+7{digits[1:]}"
        if not re.match(r'^\+79\d{9}$', phone):
            raise ValidationError("Формат номера должен быть +79XXXXXXXXX")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        role = self.selected_role or cleaned_data.get('role')
        dob = cleaned_data.get('child_dob')
        if not role:
            raise ValidationError("Роль не выбрана.")
        if not dob:
            self.add_error('child_dob', "Укажите дату рождения")
        if not cleaned_data.get('location'):
            self.add_error('location', "Выберите город/регион")
        if role != 'V3':
            if not cleaned_data.get('child_name'):
                self.add_error('child_name', "Укажите имя и фамилию")
            if not cleaned_data.get('gender'):
                self.add_error('gender', "Укажите пол")
        if role in ['V1', 'V2']:
            if not cleaned_data.get('school_number'):
                self.add_error('school_number', "Укажите номер школы")
            if not cleaned_data.get('grade'):
                self.add_error('grade', "Укажите класс")
        if role == 'V2':
            if not cleaned_data.get('parent_name'):
                self.add_error('parent_name', "Укажите имя родителя")
            p_phone = cleaned_data.get('parent_phone')
            if not p_phone:
                self.add_error('parent_phone', "Укажите телефон родителя")
            elif self.user_phone and p_phone == self.user_phone:
                self.add_error('parent_phone', "Номер родителя не должен совпадать с вашим номером.")
        return cleaned_data


class PasswordLoginForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)

class RegistrationForm(forms.Form):
    QUESTION_CHOICES = [
        ('maiden_name', 'Девичья фамилия матери'),
        ('first_pet', 'Кличка первого питомца'),
        ('first_car', 'Марка первой машины'),
        ('favorite_book', 'Любимая книга детства'),
    ]
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold',
            'placeholder': 'Ваше имя'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold',
            'placeholder': 'Пароль'
        }),
        min_length=6
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold',
            'placeholder': 'Подтвердите пароль'
        })
    )
    security_question = forms.ChoiceField(
        choices=QUESTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold'
        })
    )
    security_answer = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold',
            'placeholder': 'Ответ на вопрос'
        })
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            if not any(char.isupper() for char in password):
                raise ValidationError("Пароль должен содержать хотя бы одну заглавную букву")
            if not any(char.isdigit() for char in password):
                raise ValidationError("Пароль должен содержать хотя бы одну цифру")
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Пароли не совпадают")
        return cleaned_data

class ResetPasswordForm(forms.Form):
    security_answer = forms.CharField(max_length=255, label="Ответ на секретный вопрос")
    password = forms.CharField(widget=forms.PasswordInput, min_length=6)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Пароли не совпадают")
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full p-4 bg-gray-50 border-2 border-gray-100 rounded-2xl outline-none focus:border-blue-500 font-bold',
                'placeholder': 'Ваше имя'
            })
        }