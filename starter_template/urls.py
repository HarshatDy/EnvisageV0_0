from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('generate/', views.generate_html_page, name='generate_html_page'),
    path('<str:page_name>/', views.show_generated_page, name='show_generated_page'),
]