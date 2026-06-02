from resume.models import EmploymentHistory

nyls = EmploymentHistory.objects.get(pk=1134715507362267137)
nyls.description_html = (
    "Created software to automate advertising generation using <strong>Python</strong> and "
    "<strong>Selenium</strong> browser automation. Over 2 million ads were served using this system."
)
nyls.save()
print("✓ NY Living Solutions updated")

de = EmploymentHistory.objects.get(pk=1134715507968278529)
de.description_html = (
    "Developed and deployed custom <strong>Python</strong> and <strong>Selenium</strong> browser "
    "automation scripts to automate advertising for a large team of agents. "
    "2x Douglas Elliman Chairman's Gold Award Winner — Total Commission Earned: The LoRusso Team (2014, 2015)"
)
de.save()
print("✓ Douglas Elliman updated")
