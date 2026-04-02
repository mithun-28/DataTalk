from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.http import JsonResponse
from .nl_sql_pipeline import run_pipeline

def chat_page(request):
    return render(request, "chat.html")

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt   # 🔥 TEMP FIX (for testing)
def process_query(request):
    if request.method == "POST":
        query = request.POST.get("query")

        print("Query received:", query)  # DEBUG

        result = run_pipeline(query)

        return JsonResponse(result)
    




    