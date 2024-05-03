from mailmerge import MailMerge
from datetime import date
from io import BytesIO

def generate_cv(data):
    template = "proposal.docx"
    document = MailMerge(template)
    today = date.today()

    # Using the data input to fill in the fields
    services = data['services']
    service_descriptions = data['service_descriptions']

    document.merge_rows('service_name', services)
    document.merge_rows('service_description_name', service_descriptions)

    document.merge(
        proposal_date=f'{today}',
        proposal_signer_name=data['proposal_signer_name'],
        proposal_signer_title=data['proposal_signer_title'],
        proposal_signer_company_name=data['proposal_signer_company_name'],
        proposal_signer_company_address=data['proposal_signer_company_address'],
        project_name=data['project_name'],
        project_location=data['project_location'],
        project_cost=data['project_cost'],
        project_retainer=data['project_retainer'],
        proposal_note=data['proposal_note'],
        account_po_number=data['account_po_number']
    )

    # Use BytesIO to handle the file in memory
    file_stream = BytesIO()
    document.write(file_stream)
    file_stream.seek(0)
    
    # # Write the output document
    document.write(f'CV.docx')