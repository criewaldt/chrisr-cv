import json
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SharedLocation, UserLocation


def login_page(request):
    if request.user.is_authenticated:
        return redirect('bonnaroo:map')
    return render(request, 'bonnaroo/login.html')


def _get_photo(user):
    try:
        social = user.social_auth.get(provider='google-oauth2')
        return social.extra_data.get('picture', '')
    except Exception:
        return ''


@login_required(login_url='/bonnaroo/')
def map_page(request):
    user = request.user
    context = {
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'photo': _get_photo(user),
    }
    return render(request, 'bonnaroo/map.html', context)


@login_required(login_url='/bonnaroo/')
def account_page(request):
    user = request.user
    context = {
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'photo': _get_photo(user),
    }
    return render(request, 'bonnaroo/account.html', context)


@login_required(login_url='/bonnaroo/')
@require_POST
def update_name(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return redirect('bonnaroo:account')
    user = request.user
    parts = name.split(' ', 1)
    user.first_name = parts[0]
    user.last_name = parts[1] if len(parts) > 1 else ''
    user.save(update_fields=['first_name', 'last_name'])
    return redirect('bonnaroo:account')


@login_required(login_url='/bonnaroo/')
@require_POST
def delete_account(request):
    user = request.user
    logout(request)
    user.delete()
    return redirect('bonnaroo:login')


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
    from social_django.models import UserSocialAuth

    social_accounts = (
        UserSocialAuth.objects
        .filter(provider='google-oauth2')
        .select_related('user')
        .prefetch_related('user__bonnaroo_location')
    )

    now = timezone.now()
    users = []
    for sa in social_accounts:
        u = sa.user
        photo = sa.extra_data.get('picture', '')

        try:
            loc = u.bonnaroo_location
            lat, lng = loc.lat, loc.lng
            delta = int((now - loc.updated_at).total_seconds())
            if delta < 60:
                last_seen = 'just now'
            elif delta < 3600:
                last_seen = f'{delta // 60}m ago'
            elif delta < 86400:
                last_seen = f'{delta // 3600}h ago'
            else:
                last_seen = loc.updated_at.strftime('%b %-d')
        except UserLocation.DoesNotExist:
            lat, lng, last_seen = None, None, 'no location yet'

        users.append({
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'photo': photo,
            'lat': lat,
            'lng': lng,
            'last_seen': last_seen,
            'is_me': u.id == request.user.id,
        })

    users.sort(key=lambda u: (u['lat'] is None, u['last_seen']))
    return JsonResponse({'users': users})


@login_required(login_url='/bonnaroo/')
def pins(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        tag  = data.get('tag', '')
        lat, lng = data.get('lat'), data.get('lng')
        if not name or lat is None or lng is None:
            return JsonResponse({'error': 'name, lat, and lng required'}, status=400)
        pin = SharedLocation.objects.create(user=request.user, name=name, tag=tag, lat=lat, lng=lng)
        return JsonResponse({'id': pin.id, 'ok': True})

    now = timezone.now()
    qs = SharedLocation.objects.select_related('user').order_by('-created_at')
    result = []
    for pin in qs:
        delta = int((now - pin.created_at).total_seconds())
        if delta < 60:
            age = 'just now'
        elif delta < 3600:
            age = f'{delta // 60}m ago'
        elif delta < 86400:
            age = f'{delta // 3600}h ago'
        else:
            age = pin.created_at.strftime('%b %-d')

        result.append({
            'id': pin.id,
            'name': pin.name,
            'tag': pin.tag,
            'lat': pin.lat,
            'lng': pin.lng,
            'creator': pin.user.get_full_name() or pin.user.username,
            'age': age,
            'is_mine': pin.user_id == request.user.id,
        })
    return JsonResponse({'pins': result})


@login_required(login_url='/bonnaroo/')
def delete_pin(request, pin_id):
    SharedLocation.objects.filter(id=pin_id, user=request.user).delete()
    return redirect('bonnaroo:map')


def logout_view(request):
    logout(request)
    return redirect('bonnaroo:login')
