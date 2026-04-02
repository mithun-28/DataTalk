from django.contrib import admin
from django.urls import path
from chatbot import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.chat_page, name='chat'),
    path('process/', views.process_query, name='process_query')
]
