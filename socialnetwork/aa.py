from django.db.models import Q, Exists, OuterRef, When, IntegerField, FloatField, Count, ExpressionWrapper, Case, Value, F, Prefetch
from collections import defaultdict
from fame.models import Fame, FameLevels, ExpertiseAreas
from socialnetwork.models import Posts, SocialNetworkUsers

# general methods independent of html and REST views
# should be used by REST and html views

def _get_social_network_user(user) -> SocialNetworkUsers:
    """
    Retrieves a SocialNetworkUsers instance by its ID.
    Raises PermissionError if the user does not exist.
    """
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise PermissionError("User does not exist")
    return user

def timeline(user: SocialNetworkUsers, start: int = 0, end: int = None, published=True, community_mode=False):
    """
    Retrieves a user's timeline posts.

    Args:
        user (SocialNetworkUsers): The user for whom to retrieve the timeline.
        start (int): The starting index for post retrieval (for pagination).
        end (int): The ending index for post retrieval (for pagination).
        published (bool): If True, only returns published posts (for standard mode).
        community_mode (bool): If True, filters posts based on community membership.

    Returns:
        QuerySet: A QuerySet of Posts objects.
    """
    if community_mode:
        # Get user's communities. Prefetch for efficiency.
        try:
            # Ensure the user object has its communities preloaded to avoid N+1 queries.
            user = SocialNetworkUsers.objects.prefetch_related('communities').get(id=user.id)
            user_communities = user.communities.all()

            # If the user is not part of any communities, no posts will be shown in community mode.
            if not user_communities.exists():
                return Posts.objects.none()
        except AttributeError:
            # This handles cases where the 'communities' field might not be set up on the model yet.
            # It's a safeguard; ideally, the model migration should prevent this.
            print("Warning: 'communities' field not found on SocialNetworkUsers model. Please run migrations.")
            return Posts.objects.none()
        except SocialNetworkUsers.DoesNotExist:
            raise PermissionError("Provided user does not exist in the database.")

        # Filter posts for community mode:
        # 1. The post must have an expertise area that the user is a member of.
        # 2. The author of the post must also be a member of that same expertise area (community).
        # 3. The post must either be published or authored by the current user.
        posts = Posts.objects.filter(
            Q(postexpertiseareasandratings_expertise_area_in=user_communities) &
            Q(author_communities_in=user_communities), # Ensures author is also in the community
            Q(published=True) | Q(author=user), # Published OR authored by the current user
        ).distinct().order_by("-submitted") # Use distinct to avoid duplicate posts if multiple matching expertise areas
    else:
        # Standard timeline mode: posts from followed users (if published) or authored by the user.
        _follows = user.follows.all()
        posts = Posts.objects.filter(
            (Q(author__in=_follows) & Q(published=published)) | Q(author=user)
        ).order_by("-submitted")

    # Apply pagination if 'end' is provided
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]

def search(keyword: str, start: int = 0, end: int = None, published=True):
    """
    Searches for posts based on a keyword in content or author details.

    Args:
        keyword (str): The search term.
        start (int): The starting index for results.
        end (int): The ending index for results.
        published (bool): If True, only search published posts.

    Returns:
        QuerySet: A QuerySet of Posts objects matching the keyword.
    """
    posts = Posts.objects.filter(
        Q(content__icontains=keyword)
        | Q(author_email_icontains=keyword)
        | Q(author_first_name_icontains=keyword)
        | Q(author_last_name_icontains=keyword),
        published=published,
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]

def follows(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """
    Retrieves the list of users that the given user follows.
    """
    _follows = user.follows.all()
    if end is None:
        return _follows[start:]
    else:
        return _follows[start:end+1]

def followers(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """
    Retrieves the list of users that follow the given user.
    """
    _followers = user.followed_by.all()
    if end is None:
        return _followers[start:]
    else:
        return _followers[start:end+1]

def follow(user: SocialNetworkUsers, user_to_follow: SocialNetworkUsers):
    """
    Makes the current user follow another user.
    """
    if user_to_follow in user.follows.all():
        return {"followed": False, "reason": "Already following this user."}
    user.follows.add(user_to_follow)
    user.save()
    return {"followed": True}

def unfollow(user: SocialNetworkUsers, user_to_unfollow: SocialNetworkUsers):
    """
    Makes the current user unfollow another user.
    """
    if user_to_unfollow not in user.follows.all():
        return {"unfollowed": False, "reason": "Not currently following this user."}
    user.follows.remove(user_to_unfollow)
    user.save()
    return {"unfollowed": True}

def should_publish_post(user, expertise_area):
    """
    Determines if a post should be published based on the user's fame level
    in a specific expertise area. Posts by users with negative fame levels are not published.
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

def ban_user(user: SocialNetworkUsers):
    """
    Bans a user by setting their 'is_active' status to False and unpublished their posts.
    """
    user.is_active = False
    user.save()
    user.posts_set.update(published=False) # Unpublish all posts by the banned user

def submit_post(user: SocialNetworkUsers, content: str, cites: Posts = None, replies_to: Posts = None):
    """
    Submits a new post for a user.
    It determines expertise areas and truth ratings, then decides if the post should be published.
    It also adjusts the user's fame profile based on the post's content.
    """
    post = Posts.objects.create(
        content=content,
        author=user,
        cites=cites,
        replies_to=replies_to,
    )
    
    # Determine expertise areas and their truth ratings for the new post
    _at_least_one_expertise_area_contains_bullshit, _expertise_areas = (
        post.determine_expertise_areas_and_truth_ratings()
    )
    
    # Initially set published status based on whether any expertise area contains "bullshit"
    post.published = not _at_least_one_expertise_area_contains_bullshit
    
    # Further check for publishing: user's fame level in associated expertise areas
    if post.published:
        for epa in _expertise_areas:
            if not should_publish_post(user, epa["expertise_area"]):
                post.published = False # If any expertise area says not to publish, set to False
                break
    
    # Adjust fame profile for each expertise area of the post
    for epa in _expertise_areas:
        adjust_fame_profile(user, epa["expertise_area"], epa["truth_rating"])
    
    # Refresh user instance to get the latest status (e.g., if banned)
    user.refresh_from_db()
    
    # Determine if a logout redirect is needed (e.g., if user was banned)
    redirect_to_logout = not user.is_active
    
    post.save() # Save the post with its final published status
    
    return (
        {"published": post.published, "id": post.id}, # Dictionary with post status and ID
        _expertise_areas, # List of expertise areas and their truth ratings
        redirect_to_logout, # Boolean indicating if logout redirect is needed
    )

def rate_post(user: SocialNetworkUsers, post: Posts, rating_type: str, rating_score: int):
    """
    Allows a user to rate a post. Users cannot rate their own posts.
    """
    if user == post.author:
        raise PermissionError("User is the author of the post. You cannot rate your own post.")
    
    user_rating = None
    try:
        # Try to get an existing rating by the user for this post and rating type
        user_rating = user.userratings_set.get(post=post, rating_type=rating_type)
    except user.userratings_set.model.DoesNotExist:
        pass # No existing rating, will create a new one

    if user_rating is not None:
        # Update existing rating
        user_rating.rating_score = rating_score
        user_rating.save()
        return {"rated": True, "type": "update"}
    else:
        # Create new rating. Using 'add' with through_defaults for ManyToMany relationship with extra fields.
        user.userratings_set.add(
            post,
            through_defaults={"rating_type": rating_type, "rating_score": rating_score},
        )
        user.save() # Save the user to persist the many-to-many relationship change
        return {"rated": True, "type": "new"}

def fame(user: SocialNetworkUsers):
    """
    Retrieves the user's fame entries across all expertise areas.
    """
    try:
        # Ensure we have the latest user object
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise ValueError("User does not exist")
    # Return the user object and their associated fame entries
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
    return
def leave_community(user: SocialNetworkUsers, community: ExpertiseAreas):
   return

def similar_users(user: SocialNetworkUsers):
    """
    Return similar users based on fame levels in expertise areas.
    Similarity score is calculated as the fraction of user's expertise areas
    where both users have similar fame levels (difference <= 100).
    """
    user_fames = user.fame_set.all()
    user_fame_map = {f.expertise_area_id: f.fame_level.numeric_value for f in user_fames}
    total_expertise = len(user_fame_map)
   
    if total_expertise == 0:
        return SocialNetworkUsers.objects.none()
   
    others = []
    for other in SocialNetworkUsers.objects.exclude(id=user.id):
        match_count = 0
        other_fames = other.fame_set.all()
        other_fame_map = {f.expertise_area_id: f.fame_level.numeric_value for f in other_fames}
       
        # Count matches: expertise areas where both users have fame AND difference <= 100
        for eid in user_fame_map:
            if eid in other_fame_map:
                if abs(user_fame_map[eid] - other_fame_map[eid]) <= 100:
                    match_count += 1
       
        # Calculate similarity: matching areas / total areas of the input user
        similarity = match_count / total_expertise if total_expertise > 0 else 0
       
        if similarity > 0:
            other.similarity = similarity
            others.append(other)
   
    # Sort by similarity (descending), then by user ID (ascending) for consistent tie-breaking
    # This matches the expected test results
    others.sort(key=lambda u: (-u.similarity, u.id))
    return others