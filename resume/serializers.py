from rest_framework import serializers
from .models import Resume, ProfessionalSummary, EmploymentHistory, Award, Education, Keyword

class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = "__all__"
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation

class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = "__all__"
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation

class ProfessionalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalSummary
        fields = ['summary', 'highlights']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation



class EmploymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentHistory
        fields = ['job_title', 'company_name', 'location', 'start_date', 'end_date', 'description', 'is_current', 'sort_order'] 
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        
        return representation



class ResumeSerializer(serializers.ModelSerializer):
    professional_summary = ProfessionalSummarySerializer()
    employment_history = EmploymentHistorySerializer(many=True, read_only=True)
    education = EducationSerializer(many=True, read_only=True)
    awards = AwardSerializer(many=True, read_only=True)
    keywords = KeywordSerializer(many=True, read_only=True)

    class Meta:
        model = Resume
        fields = ['name', 'email', 'phone', 'desired_title', 'current_title', 'professional_summary', 'employment_history', 'education', 'awards', 'keywords']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response

        # Sort employment history by 'sort_order' field in ascending order
        if 'employment_history' in representation:
            representation['employment_history'] = sorted(
                representation['employment_history'],
                key=lambda x: x.get('sort_order', 0)
            )
        
        return representation


    
