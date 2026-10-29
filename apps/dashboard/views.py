import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from . import services


@login_required
def index_view(request):
    """
    Renders the clinical and epidemiological dashboard view.
    Supplies real aggregated patient evaluation records computed
    from the clinical PostgreSQL models.
    """
    data = services.get_dashboard_evaluation_data()
    context = {
        'total_evaluated': data['total'],
        'available_years': data['years'],
        'available_categories': data['categories'],
        'records_json': json.dumps(data['records']),
    }
    return render(request, "dashboard/index.html", context)


@login_required
def api_dashboard_data(request):
    """
    JSON API endpoint returning the dynamic cohort records and slicer metadata
    computed from real database records.
    """
    data = services.get_dashboard_evaluation_data()
    return JsonResponse({
        'status': 'success',
        'total': data['total'],
        'years': data['years'],
        'categories': data['categories'],
        'records': data['records'],
    })
