from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from . import services
from security.access import clinical_access_required


@login_required
@clinical_access_required('read')
def index_view(request):
    """
    Renders the clinical and epidemiological dashboard view.
    Supplies real aggregated patient evaluation records computed
    from the clinical PostgreSQL models across all 8 clinical blocks.
    """
    data = services.get_dashboard_evaluation_data()
    context = {
        'total_evaluated': data['total'],
        'summary_kpis': data['summary_kpis'],
        'module_kpis': data['module_kpis'],
        'available_years': data['years'],
        'available_categories': data['categories'],
        'available_institutions': data['institutions'],
        'available_fichas': data['fichas'],
        'records': data['records'],
    }
    return render(request, "dashboard/index.html", context)


@login_required
@clinical_access_required('read', api=True)
def api_dashboard_data(request):
    """
    JSON API endpoint returning the dynamic cohort records and slicer metadata
    computed from real database records.
    """
    data = services.get_dashboard_evaluation_data()
    return JsonResponse({
        'status': 'success',
        'total': data['total'],
        'summary_kpis': data['summary_kpis'],
        'module_kpis': data['module_kpis'],
        'years': data['years'],
        'categories': data['categories'],
        'institutions': data['institutions'],
        'fichas': data['fichas'],
        'records': data['records'],
    })
