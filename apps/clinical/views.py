from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def form_view(request):
    """
    Renders the clinical evaluation form template.
    TODO: Connect form submission and data population with Clinical ORM models.
    Currently form.js operates with local test/mock data.
    """
    return render(request, 'clinical/form.html')


@login_required
def list_view(request):
    """
    Renders the patients directory and medical evaluations list.
    TODO: Connect directory search, filters, and modals with Clinical ORM models.
    Currently pacientes.js and list.js operate with local test/mock data.
    """
    return render(request, 'clinical/list.html')
