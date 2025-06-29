from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from socialnetwork import api
from socialnetwork.api import _get_social_network_user
from socialnetwork.models import SocialNetworkUsers
from socialnetwork.serializers import PostsSerializer


@require_http_methods(["GET"])
@login_required
def timeline(request):
    # using the serializer to get the data, then use JSON in the template!
    # avoids having to do the same thing twice

    # initialize community mode to False the first time in the session
    if 'community_mode' not in request.session:
        request.session['community_mode'] = False


    # get extra URL parameters:
    keyword = request.GET.get("search", "")
    published = request.GET.get("published", True)
    error = request.GET.get("error", None)

    # if keyword is not empty, use search method of API:
    if keyword and keyword != "":
        context = {
            "posts": PostsSerializer(
                api.search(keyword, published=published), many=True
            ).data,
            "searchkeyword": keyword,
            "error": error,
            "followers": list(api.follows(_get_social_network_user(request.user)).values_list('id', flat=True)),
        }
    else:  # otherwise, use timeline method of API:

        context = {
            "posts": PostsSerializer(
                api.timeline(
                    _get_social_network_user(request.user),
                    published=published,
                ),
                many=True,
            ).data,
            "searchkeyword": "",
            "error": error,
            "followers": list(api.follows(_get_social_network_user(request.user)).values_list('id', flat=True)),
        }

    return render(request, "timeline.html", context=context)


@require_http_methods(["POST"])
@login_required
def follow(request):
    user = _get_social_network_user(request.user)
    user_to_follow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.follow(user, user_to_follow)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["POST"])
@login_required
def unfollow(request):
    user = _get_social_network_user(request.user)
    user_to_unfollow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.unfollow(user, user_to_unfollow)
    return redirect(reverse("sn:timeline"))




#Task 6 Starts here, HTML VIEW OF BULLSHITTERS.API




@require_http_methods(["GET"])
@login_required
def bullshitters(request):
    # Call the API to get a dictionary mapping expertise areas to lists of users with negative fame
    bs_data = api.bullshitters()
    # Sort the expertise areas alphabetically for a consistent display order
    sorted_expertise_areas = sorted(bs_data.keys(), key=lambda ea: str(ea))
    # Prepare the context for the template, including the sorted areas and the mapping
    bullshitters_by_area = [(area, bs_data[area]) for area in sorted_expertise_areas]
    context = {
        "bullshitters_by_area": bullshitters_by_area,  # List of (expertise_area, entries) tuples
    }
    # Render the bullshitters.html template with the context data
    return render(request, "bullshitters.html", context)



@require_http_methods(["POST"])
@login_required
def toggle_community_mode(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["POST"])
@login_required
def join_community(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["POST"])
@login_required
def leave_community(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["GET"])
@login_required
def similar_users(request):
    """
    Display users that are similar to the current user based on expertise areas.
    """
    user = _get_social_network_user(request.user)
    similar = api.similar_users(user)
    
    context = {
        "similar_users": similar,
        "current_user": user,
        "has_results": len(similar) > 0
    }
    
    return render(request, "similar_users.html", context)
