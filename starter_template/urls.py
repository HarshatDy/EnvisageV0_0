from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('generate/', views.get_page, name='generate_html_page'),
    path('<str:page_name>/', views.homepage, name='show_generated_page'),
]