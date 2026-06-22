import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Participant, Payment, Session


def create_session(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        participants_raw = request.POST.get('participants', '').strip()

        if not name:
            return render(request, 'reimbursable/create.html', {'error': 'Session name is required.'})

        names = [n.strip() for n in participants_raw.split(',') if n.strip()]
        if len(names) < 2:
            return render(request, 'reimbursable/create.html', {
                'error': 'At least 2 people are required.',
                'name': name,
                'participants': participants_raw,
            })

        if len(names) != len(set(names)):
            return render(request, 'reimbursable/create.html', {
                'error': 'Names must be unique.',
                'name': name,
                'participants': participants_raw,
            })

        session = Session.objects.create(name=name)
        for pname in names:
            Participant.objects.create(session=session, name=pname)

        return redirect('reimbursable:session_detail', code=session.code)

    return render(request, 'reimbursable/create.html')


def session_detail(request, code):
    session = get_object_or_404(Session, code=code)
    participants = list(session.participants.order_by('id'))
    payments = list(
        session.payments
        .select_related('paid_by', 'to_participant')
        .order_by('-created_at')
    )

    settlements = _calculate_settlements(participants, payments)
    total_shared = sum(p.amount for p in payments if not p.is_direct)

    return render(request, 'reimbursable/session.html', {
        'session': session,
        'participants': participants,
        'payments': payments,
        'settlements': settlements,
        'total_shared': total_shared,
    })


@require_POST
def add_payment(request, code):
    session = get_object_or_404(Session, code=code)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    paid_by_id = data.get('paid_by')
    amount_str = data.get('amount', '')
    payment_type = data.get('type', 'entity')
    to_entity = (data.get('to_entity') or '').strip()
    to_participant_id = data.get('to_participant')
    notes = (data.get('notes') or '').strip()

    try:
        amount = Decimal(str(amount_str))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'error': 'Amount must be a positive number.'}, status=400)

    paid_by = session.participants.filter(id=paid_by_id).first()
    if not paid_by:
        return JsonResponse({'error': 'Invalid payer.'}, status=400)

    to_participant = None
    if payment_type == 'person':
        to_participant = session.participants.filter(id=to_participant_id).first()
        if not to_participant:
            return JsonResponse({'error': 'Invalid recipient.'}, status=400)
        if to_participant.id == paid_by.id:
            return JsonResponse({'error': 'Cannot pay yourself.'}, status=400)
        to_entity = ''
    else:
        if not to_entity:
            return JsonResponse({'error': 'Enter what the payment was for.'}, status=400)
        if len(to_entity) > 200:
            return JsonResponse({'error': 'Description too long.'}, status=400)

    payment = Payment.objects.create(
        session=session,
        paid_by=paid_by,
        amount=amount,
        to_entity=to_entity,
        to_participant=to_participant,
        notes=notes,
    )

    return JsonResponse({
        'ok': True,
        'payment': {
            'id': payment.id,
            'paid_by': paid_by.name,
            'amount': str(payment.amount),
            'to_entity': payment.to_entity,
            'to_participant': to_participant.name if to_participant else None,
            'notes': payment.notes,
            'is_direct': payment.is_direct,
        },
    })


@require_POST
def delete_payment(request, code, payment_id):
    session = get_object_or_404(Session, code=code)
    session.payments.filter(id=payment_id).delete()
    return JsonResponse({'ok': True})


@require_POST
def add_participant(request, code):
    session = get_object_or_404(Session, code=code)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required.'}, status=400)
    if len(name) > 100:
        return JsonResponse({'error': 'Name is too long.'}, status=400)

    if session.participants.filter(name=name).exists():
        return JsonResponse({'error': 'That name is already in this session.'}, status=400)

    p = Participant.objects.create(session=session, name=name)
    return JsonResponse({'ok': True, 'id': p.id, 'name': p.name})


def get_settlements(request, code):
    session = get_object_or_404(Session, code=code)
    participants = list(session.participants.order_by('id'))
    payments = list(
        session.payments
        .select_related('paid_by', 'to_participant')
        .all()
    )
    settlements = _calculate_settlements(participants, payments)
    total_shared = sum(p.amount for p in payments if not p.is_direct)
    return JsonResponse({
        'settlements': [
            {'from': s['from'], 'to': s['to'], 'amount': str(s['amount'])}
            for s in settlements
        ],
        'total_shared': str(total_shared),
    })


def _calculate_settlements(participants, payments):
    """
    All shared expenses (payments to outside entities) are split equally
    among all participants. Direct payments between people are credits/debits.
    Returns a list of single payments that settle all debts.
    """
    if not participants:
        return []

    n = len(participants)
    balances = {p.id: Decimal('0') for p in participants}
    name_map = {p.id: p.name for p in participants}

    for payment in payments:
        if payment.is_direct:
            balances[payment.paid_by_id] += payment.amount
            balances[payment.to_participant_id] -= payment.amount
        else:
            share = payment.amount / n
            balances[payment.paid_by_id] += payment.amount
            for p in participants:
                balances[p.id] -= share

    creditors = []
    debtors = []
    for pid, balance in balances.items():
        rounded = balance.quantize(Decimal('0.01'))
        if rounded > 0:
            creditors.append([pid, rounded])
        elif rounded < 0:
            debtors.append([pid, -rounded])

    creditors.sort(key=lambda x: -x[1])
    debtors.sort(key=lambda x: -x[1])

    settlements = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        amount = min(creditors[i][1], debtors[j][1])
        if amount > 0:
            settlements.append({
                'from': name_map[debtors[j][0]],
                'to': name_map[creditors[i][0]],
                'amount': amount,
            })
        creditors[i][1] -= amount
        debtors[j][1] -= amount
        if creditors[i][1] <= 0:
            i += 1
        if debtors[j][1] <= 0:
            j += 1

    return settlements
