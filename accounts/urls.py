from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import LoggedOutTemplateView, SignUpView

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", LoggedOutTemplateView.as_view(), name="logout"),
    path("signup/", SignUpView.as_view(), name="signup"),
]
