from django.db import models
from bs4 import BeautifulSoup

def strip_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return text

class ProfessionalSummary(models.Model):
    summary_html = models.TextField()
    highlights = models.TextField()
    
    @property
    def summary(self):
        return strip_html(self.summary_html)

    def __str__(self):
        return self.summary
    
class Award(models.Model):
    name = models.CharField(max_length=100, blank=False)
    description = models.TextField(blank=True)
    def __str__(self):
        return self.name

class EmploymentHistory(models.Model):
    job_title = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description_html = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)

    @property
    def description(self):
        return strip_html(self.description_html)

    def __str__(self):
        return self.company_name

class Education(models.Model):
    degree = models.CharField(max_length=100)
    school = models.CharField(max_length=100)
    time = models.CharField(max_length=100)

    def __str__(self):
        return self.degree

class Resume(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    current_title = models.CharField(max_length=100, blank=True, null=True)
    desired_title = models.CharField(max_length=100, blank=True, null=True)
    professional_summary = models.ForeignKey(ProfessionalSummary, on_delete=models.CASCADE)
    employment_history = models.ManyToManyField(EmploymentHistory)
    awards = models.ManyToManyField(Award)
    education = models.ManyToManyField(Education)

    def __str__(self):
        return self.name
