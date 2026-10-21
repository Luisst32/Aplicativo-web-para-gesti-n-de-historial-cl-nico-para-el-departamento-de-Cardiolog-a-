from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def index_view(request):
    """
    Renders the clinical and epidemiological dashboard view.
    Consumes test data from static/dashboard/js/dashboard-data.js.
    """
    return render(request, "dashboard/index.html")
