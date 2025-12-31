# decoder/views.py
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import PocsagMessage, ListenerStatus


# Limites autorisées pour le nombre de messages
ALLOWED_LIMITS = [20, 50, 100, 150, 200, 500, 1000]
DEFAULT_LIMIT = 50


def get_dedupe_minutes():
    """
    Récupère le temps de déduplication configuré.
    Priorité: cache Django > fichier config > valeur par défaut (3 min)
    """
    default_minutes = 3
    
    # Essayer le cache Django
    try:
        from django.core.cache import cache
        cached_value = cache.get('pocsag_dedupe_minutes')
        if cached_value is not None:
            return int(cached_value)
    except Exception:
        pass
    
    # Essayer le fichier de configuration
    try:
        import os
        config_path = os.path.join(settings.BASE_DIR, '.pocsag_config')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return int(f.read().strip())
    except Exception:
        pass
    
    return default_minutes


def get_limit_from_request(request):
    """
    Récupère et valide le paramètre limit depuis la requête.
    Retourne une valeur autorisée ou la valeur par défaut.
    """
    try:
        limit = int(request.GET.get('limit', DEFAULT_LIMIT))
        if limit in ALLOWED_LIMITS:
            return limit
    except (ValueError, TypeError):
        pass
    return DEFAULT_LIMIT


def index(request):
    limit = get_limit_from_request(request)
    messages = get_deduplicated_messages()[:limit]
    status = ListenerStatus.get_status()
    dedupe_minutes = get_dedupe_minutes()
    return render(request, 'decoder/index.html', {
        'messages': messages,
        'listener_status': status,
        'dedupe_minutes': dedupe_minutes,
        'current_limit': limit
    })


def get_deduplicated_messages(address_filter='', date_filter='', search_filter=''):
    """
    Récupère les messages en éliminant les doublons :
    - Même adresse + même message + intervalle < X minutes = doublon
    Le temps de déduplication est configurable via listen_pocsag.py
    """
    # Récupérer le temps de déduplication configuré
    dedupe_minutes = get_dedupe_minutes()
    
    # Commencer avec tous les messages triés par date croissante
    messages = PocsagMessage.objects.all()

    # Appliquer les filtres AVANT la déduplication
    if address_filter:
        messages = messages.filter(address__icontains=address_filter)

    if date_filter:
        messages = messages.filter(timestamp__date=date_filter)

    if search_filter:
        messages = messages.filter(
            Q(message__icontains=search_filter) |
            Q(address__icontains=search_filter)
        )

    # Trier par timestamp pour la déduplication
    messages = messages.order_by('timestamp')

    # Déduplication
    seen = {}  # Clé: (address, message), Valeur: dernier timestamp
    deduplicated = []

    for msg in messages:
        key = (msg.address, msg.message)

        if key in seen:
            # Calculer la différence de temps
            time_diff = msg.timestamp - seen[key]

            # Si plus de X minutes (configurable), on garde ce message
            if time_diff >= timedelta(minutes=dedupe_minutes):
                deduplicated.append(msg)
                seen[key] = msg.timestamp
            # Sinon, on ignore (c'est un doublon)
        else:
            # Premier message avec cette combinaison
            deduplicated.append(msg)
            seen[key] = msg.timestamp

    # Retourner dans l'ordre anti-chronologique (plus récent en premier)
    deduplicated.reverse()

    return deduplicated


def get_messages(request):
    # Récupérer les paramètres de filtre
    address_filter = request.GET.get('address', '').strip()
    date_filter = request.GET.get('date', '').strip()
    search_filter = request.GET.get('search', '').strip()
    limit = get_limit_from_request(request)

    # Obtenir les messages dédupliqués et filtrés
    messages = get_deduplicated_messages(address_filter, date_filter, search_filter)

    # Limiter aux N résultats demandés
    messages = messages[:limit]

    html = ""
    for msg in messages:
        local_date_time = msg.timestamp.astimezone(timezone.get_current_timezone())
        html += f"""
        <tr>
            <td style="width: 15%">{local_date_time.strftime('%d/%m/%Y %H:%M:%S')}</td>
            <td style="width: 7%"><code>{msg.address}</code></td>
            <td>{msg.message}</td>
        </tr>
        """

    if not html:
        html = """
        <tr>
            <td colspan="4" class="text-center text-muted">
                <em>Aucun message ne correspond aux critères de filtre...</em>
            </td>
        </tr>
        """

    return HttpResponse(html)


def get_status(request):
    """Retourne le badge de statut mis à jour avec infos de configuration"""
    status = ListenerStatus.get_status()

    if status.is_running:
        badge_class = "bg-success"
        status_text = "En ligne"
        icon = "●"
    else:
        badge_class = "bg-danger"
        status_text = "Hors ligne"
        icon = "●"

    html = f'<span class="badge {badge_class} status-badge">{icon} {status_text}</span>'
    return HttpResponse(html)
