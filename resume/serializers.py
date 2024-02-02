from rest_framework import serializers
from .models import Resume, ProfessionalSummary, EmploymentHistory, Award, Education

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

class ProfessionalSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalSummary
        fields = "__all__"
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation

class EmploymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentHistory
        fields = "__all__"
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation

class ResumeSerializer(serializers.ModelSerializer):
    professional_summary = ProfessionalSummarySerializer()
    employment_history = EmploymentHistorySerializer(read_only=True, many=True)
    education = EducationSerializer(many=True, read_only=True)
    awards = AwardSerializer(many=True, read_only=True)

    class Meta:
        model = Resume
        fields = ['name', 'email', 'phone', 'desired_title', 'current_title', 'professional_summary', 'employment_history', 'education', 'awards']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.pop('id', None)  # Remove 'id' from the response
        return representation


    
