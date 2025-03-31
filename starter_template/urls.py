from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('login/', views.login, name='login'),
    # path('generate/', views.get_page, name='generate_html_page'),
    path('<str:page_name>/', views.show_generated_page, name='show_generated_page'),
]


def add_url(url_pattern, name, views_func):
    urlpatterns.append(path(f'/{url_pattern}', views.views_func, name=name))
    print(f" THIS Are the new URLS {url_pattern}")
