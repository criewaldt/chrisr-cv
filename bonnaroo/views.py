import json
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import UserLocation


def login_page(request):
    if request.user.is_authenticated:
        return redirect('bonnaroo:map')
    return render(request, 'bonnaroo/login.html')


@login_required(login_url='/bonnaroo/')
def map_page(request):
    user = request.user
    try:
        social = user.social_auth.get(provider='google-oauth2')
        photo = social.extra_data.get('picture', '')
    except Exception:
        photo = ''

    context = {
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'photo': photo,
    }
    return render(request, 'bonnaroo/map.html', context)


@login_required(login_url='/bonnaroo/')
def update_location(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    lat, lng = data.get('lat'), data.get('lng')
    if lat is None or lng is None:
        return JsonResponse({'error': 'lat and lng required'}, status=400)

    UserLocation.objects.update_or_create(
        user=request.user,
        defaults={'lat': lat, 'lng': lng},
    )
    return JsonResponse({'ok': True})


@login_required(login_url='/bonnaroo/')
def all_users(request):
    locations = (
        UserLocation.objects
        .select_related('user')
        .prefetch_related('user__social_auth')
        .order_by('-updated_at')
    )

    now = timezone.now()
    users = []
    for loc in locations:
        u = loc.user
        try:
            social = u.social_auth.get(provider='google-oauth2')
            photo = social.extra_data.get('picture', '')
        except Exception:
            photo = ''

        delta = int((now - loc.updated_at).total_seconds())
        if delta < 60:
            last_seen = 'just now'
        elif delta < 3600:
            last_seen = f'{delta // 60}m ago'
        elif delta < 86400:
            last_seen = f'{delta // 3600}h ago'
        else:
            last_seen = loc.updated_at.strftime('%b %-d')

        users.append({
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'photo': photo,
            'lat': loc.lat,
            'lng': loc.lng,
            'last_seen': last_seen,
            'is_me': u.id == request.user.id,
        })

    users.append({
        'id': 'test',
        'name': 'Test User',
        'photo': '',
        'lat': 32.7891,
        'lng': -79.9834,
        'last_seen': 'always here',
        'is_me': False,
    })

    return JsonResponse({'users': users})


def logout_view(request):
    logout(request)
    return redirect('bonnaroo:login')
