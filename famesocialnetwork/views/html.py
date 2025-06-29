from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView, LoginView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from socialnetwork.api import _get_social_network_user


@require_http_methods(["GET"])
@login_required
def home(request):
    """
    View for the home page that includes links to various app features.
    """
    # Get any existing context or create a new one
    context = {
        # Add any existing context items here

        # Add links to important pages
        'navigation_links': [
            {'title': 'Timeline', 'url': '/sn/html/timeline'},
            {'title': 'Bullshitters List', 'url': '/sn/html/bullshitters'},
            # Add more links as needed
        ]
    }

    return render(request, "index.html", context)


class MyLoginView(LoginView):
    def form_valid(self, form):
        response = super().form_valid(form)
        return response


class MyLogoutView(LogoutView):
    next_page = reverse_lazy("auth:login")
