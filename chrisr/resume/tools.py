import json
from django.core import serializers
from django.http import HttpResponse
from resume.models import Resume, ProfessionalSummary, EmploymentHistory, Education, Award, Keyword

def dump_data(request):
    data = {
        "resume": serializers.serialize("json", Resume.objects.all()),
        "professional_summary": serializers.serialize("json", ProfessionalSummary.objects.all()),
        "employment_history": serializers.serialize("json", EmploymentHistory.objects.all()),
        "education": serializers.serialize("json", Education.objects.all()),
        "awards": serializers.serialize("json", Award.objects.all()),
        "keywords": serializers.serialize("json", Keyword.objects.all()),
    }
    response = HttpResponse(json.dumps(data, indent=4), content_type="application/json")
    response['Content-Disposition'] = 'attachment; filename="db_dump.json"'
    return response

from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view
from .serializers import ResumeSerializer
import json

@api_view(['POST'])
def upload_resume_data(request):
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES['file']
            data = json.load(uploaded_file)
            resume_serializer = ResumeSerializer(data=data)
            if resume_serializer.is_valid():
                resume_serializer.save()
                return JsonResponse({"message": "Data loaded successfully."},
                                    status=201)
            else:
                return JsonResponse(resume_serializer.errors, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid request method."}, status=405)

from django.shortcuts import render

def upload_form(request):
    return render(request, 'upload.html')
