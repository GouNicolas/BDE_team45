from django.db.models import Q, Exists, OuterRef, When, IntegerField, FloatField, Count, ExpressionWrapper, Case, Value, F, Prefetch

from fame.models import Fame, FameLevels, FameUsers, ExpertiseAreas
from socialnetwork.models import Posts, SocialNetworkUsers


# general methods independent of html and REST views
# should be used by REST and html views


def _get_social_network_user(user) -> SocialNetworkUsers:
    """Given a FameUser, gets the social network user from the request. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise PermissionError("User does not exist")
    return user


def timeline(user: SocialNetworkUsers, start: int = 0, end: int = None, published=True, community_mode=False):
    """Get the timeline of the user. Assumes that the user is authenticated."""

    if community_mode:
        # T4
        # in community mode, posts of communities are displayed if ALL of the following criteria are met:
        # 1. the author of the post is a member of the community
        # 2. the user is a member of the community
        # 3. the post contains the community’s expertise area
        # 4. the post is published or the user is the author

        pass
        #########################
        # add your code here
        #########################

    else:
        # in standard mode, posts of followed users are displayed
        _follows = user.follows.all()
        posts = Posts.objects.filter(
            (Q(author__in=_follows) & Q(published=published)) | Q(author=user)
        ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def search(keyword: str, start: int = 0, end: int = None, published=True):
    """Search for all posts in the system containing the keyword. Assumes that all posts are public"""
    posts = Posts.objects.filter(
        Q(content__icontains=keyword)
        | Q(author__email__icontains=keyword)
        | Q(author__first_name__icontains=keyword)
        | Q(author__last_name__icontains=keyword),
        published=published,
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def follows(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the users followed by this user. Assumes that the user is authenticated."""
    _follows = user.follows.all()
    if end is None:
        return _follows[start:]
    else:
        return _follows[start:end+1]


def followers(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the followers of this user. Assumes that the user is authenticated."""
    _followers = user.followed_by.all()
    if end is None:
        return _followers[start:]
    else:
        return _followers[start:end+1]


def follow(user: SocialNetworkUsers, user_to_follow: SocialNetworkUsers):
    """Follow a user. Assumes that the user is authenticated. If user already follows the user, signal that."""
    if user_to_follow in user.follows.all():
        return {"followed": False}
    user.follows.add(user_to_follow)
    user.save()
    return {"followed": True}


def unfollow(user: SocialNetworkUsers, user_to_unfollow: SocialNetworkUsers):
    """Unfollow a user. Assumes that the user is authenticated. If user does not follow the user anyway, signal that."""
    if user_to_unfollow not in user.follows.all():
        return {"unfollowed": False}
    user.follows.remove(user_to_unfollow)
    user.save()
    return {"unfollowed": True}

# functions used for T1 and T2
def should_publish_post(user, expertise_area):
    """
    Check if a post should be published based on the user's fame profile.
    Do not publish posts that have an expertise area marked negative in the user's fame profile.
    """
    fame_entry = user.fame_set.filter(expertise_area=expertise_area).first()
    if fame_entry and fame_entry.fame_level.numeric_value < 0:
        return False
    return True


def adjust_fame_profile(user: SocialNetworkUsers, expertise_area: ExpertiseAreas, truth_rating):
    """
    Adjusts a user's fame profile in a given expertise area based on a truth rating.
    If the truth rating is negative, the user's fame level may decrease.
    If a user's fame level drops below "Super Pro" in a community they are part of,
    they are automatically removed from that community.
    """
    # Only adjust if a truth rating is provided and it's negative
    if truth_rating and truth_rating.numeric_value < 0:
        fame_entry = user.fame_set.filter(expertise_area=expertise_area).first()
        super_pro_level = FameLevels.objects.get(name="Super Pro")
        super_pro_value = super_pro_level.numeric_value

        if fame_entry:
            # Find the next lower fame level based on numeric_value
            lower_fame_level = FameLevels.objects.filter(
                numeric_value__lt=fame_entry.fame_level.numeric_value
            ).order_by("-numeric_value").first()

            if lower_fame_level:
                # Decrease the fame level if a lower one exists
                fame_entry.fame_level = lower_fame_level
                fame_entry.save()
            else:
                # If no lower fame level, ban the user (set is_active to False)
                ban_user(user)
            
            # T4d: Automatically remove user from community if fame drops below Super Pro
            if fame_entry.fame_level.numeric_value < super_pro_value:
                # Check if 'communities' attribute exists and is not None
                if hasattr(user, 'communities') and user.communities is not None:
                    # Check if the expertise_area is one of the user's communities
                    if expertise_area in user.communities.all():
                        user.communities.remove(expertise_area)
                        user.save() # Save the user after removing from the community
        else:
            # If no fame entry exists for this expertise area and a negative truth rating is given,
            # create a "Confuser" entry for the user in this expertise area.
            confuser_level = FameLevels.objects.filter(name="Confuser").first()
            if confuser_level: # Ensure Confuser level exists
                Fame.objects.create(
                    user=user, expertise_area=expertise_area, fame_level=confuser_level
                )



def ban_user(user):
    """
    Ban a user from the social network:
    - Set `is_active` to False.
    - Log out the user if logged in.
    - Unpublish all their posts.
    """
    user.is_active = False
    user.save()

    # Unpublish all posts by the user
    user.posts_set.update(published=False)
    
# and of functions used for T1 and T2


def submit_post(
    user: SocialNetworkUsers,
    content: str,
    cites: Posts = None,
    replies_to: Posts = None,
):
    """Submit a post for publication. Assumes that the user is authenticated.
    returns a tuple of three elements:
    1. a dictionary with the keys "published" and "id" (the id of the post)
    2. a list of dictionaries containing the expertise areas and their truth ratings
    3. a boolean indicating whether the user was banned and logged out and should be redirected to the login page
    """

    # create post  instance:
    post = Posts.objects.create(
        content=content,
        author=user,
        cites=cites,
        replies_to=replies_to,
    )

    # classify the content into expertise areas:
    _at_least_one_expertise_area_contains_bullshit, _expertise_areas = (
        post.determine_expertise_areas_and_truth_ratings()
    )
    
    # Determine if post should be published based on content analysis and user's fame profile
    post.published = not _at_least_one_expertise_area_contains_bullshit
    
    # T1: Check if post should be published based on user's fame profile
    # to improve
    if post.published:  # Only check fame if content is not bullshit
        
        for epa in _expertise_areas:
            if not should_publish_post(user, epa["expertise_area"]):
                post.published = False
                break
    #same (opti)
    # T2: Adjust fame profile based on truth ratings
    for epa in _expertise_areas:
        adjust_fame_profile(user, epa["expertise_area"], epa["truth_rating"])

    # Refresh user state and check if user was banned after fame adjustments
    user.refresh_from_db()
    redirect_to_logout = not user.is_active

    post.save()

    return (
        {"published": post.published, "id": post.id},
        _expertise_areas,
        redirect_to_logout,
    )


def rate_post(
    user: SocialNetworkUsers, post: Posts, rating_type: str, rating_score: int
):
    """Rate a post. Assumes that the user is authenticated. If user already rated the post with the given rating_type,
    update that rating score."""
    user_rating = None
    try:
        user_rating = user.userratings_set.get(post=post, rating_type=rating_type)
    except user.userratings_set.model.DoesNotExist:
        pass

    if user == post.author:
        raise PermissionError(
            "User is the author of the post. You cannot rate your own post."
        )

    if user_rating is not None:
        # update the existing rating:
        user_rating.rating_score = rating_score
        user_rating.save()
        return {"rated": True, "type": "update"}
    else:
        # create a new rating:
        user.userratings_set.add(
            post,
            through_defaults={"rating_type": rating_type, "rating_score": rating_score},
        )
        user.save()
        return {"rated": True, "type": "new"}


def fame(user: SocialNetworkUsers):
    """Get the fame of a user. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise ValueError("User does not exist")

    return user, Fame.objects.filter(user=user)


def bullshitters():
    """
    Identifies and returns users with negative fame levels, categorized by expertise area.
    These are considered "bullshitters" in their respective areas.
    """
    result = defaultdict(list)
    # Filter for fame entries with negative numeric values, and prefetch related objects for efficiency
    negative_fame_entries = Fame.objects.filter(
        fame_level_numeric_value_lt=0
    ).select_related(
        'user', 'expertise_area', 'fame_level' # Prefetch related user, expertise_area, and fame_level objects
    ).order_by(
        'expertise_area__label', # Order by expertise area label
        'fame_level__numeric_value', # Then by fame level (ascending, more negative first)
        '-user__date_joined' # Then by date joined (most recent first) for ties
    )
    for fame_entry in negative_fame_entries:
        expertise_area = fame_entry.expertise_area
        user_info = {
            "user": fame_entry.user,
            "fame_level_numeric": fame_entry.fame_level.numeric_value
        }
        result[expertise_area].append(user_info)
    return dict(result) # Convert defaultdict to regular dict for return




def join_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Join a specified community. Note that this method does not check whether the user is eligible for joining the
    community.
    """
    pass
    #########################
    # add your code here
    #########################



def leave_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Leave a specified community."""
    pass
    #########################
    # add your code here
    #########################



def similar_users(user: SocialNetworkUsers):
    """Compute the similarity of user with all other users. The method returns a QuerySet of FameUsers annotated
    with an additional field 'similarity'. Sort the result in descending order according to 'similarity', in case
    there is a tie, within that tie sort by date_joined (most recent first)"""
    pass
    #########################
    # add your code here
    #########################

