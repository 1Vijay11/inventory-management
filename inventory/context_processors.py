#This File is for connected to the base.html as i need to setup a variable for if a ctive market is happenng show shortcuts to that market
# in settings register it :     'inventory.context_processors.active_market'

from .models import Market

def active_market(request):
    if not request.user.is_authenticated:
        return {}
    market = Market.objects.filter(user=request.user, is_active=True).first()
    return {'nav_active_market': market}