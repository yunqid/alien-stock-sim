from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from alienstocksim.forms import LoginForm, RegisterForm
from alienstocksim.models import Profile, StockEntry
import json
from django.http import JsonResponse



def landing_action(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'alienstocksim/landing.html')


# Dummy data for Sprint 1
DUMMY_CURRENT_PRICES = {
    'AAPL': 185.20,
    'TSLA': 210.40,
    'NVDA': 875.60,
    'AMZN': 178.10,
}

DUMMY_BOUGHT_AT = {
    'AAPL': 178.50,
    'TSLA': 195.00,
    'NVDA': 820.00,
    'AMZN': 165.30,
}

DEFAULT_PRICE = 100

DUMMY_HOLDINGS = [
    ('AAPL', 10, 185.20, 178.50),
    ('TSLA', 5, 210.40, 195.00),
    ('NVDA', 3, 875.60, 820.00),
    ('AMZN', 2, 178.10, 165.30),
]

# Helper functions

def _net_worth(profile, current_prices=None):
    """
    Net worth = liquid_money + sum(quantity * current_price) for each real holding.
    Only uses actual StockEntry rows in the database.
    """
    prices = current_prices or DUMMY_CURRENT_PRICES
    total = profile.liquid_money

    for entry in profile.stocks.all():
        total += entry.quantity * prices.get(entry.company, DEFAULT_PRICE)

    return total


def display_net_worth(profile):
    """
    For Sprint 1 display/demo purposes:
    - If the user has real stock entries, use them.
    - Otherwise, use dummy holdings.
    """
    if profile.stocks.exists():
        return _net_worth(profile, DUMMY_CURRENT_PRICES)

    total = profile.liquid_money
    for company, qty, curr, bought in DUMMY_HOLDINGS:
        total += qty * curr
    return total


def build_holdings_for_profile(profile):
    """
    Build holdings for display on the profile page.
    - If real holdings exist, show real holdings with dummy current prices.
    - Otherwise, show dummy holdings.
    """
    holdings = []
    real_entries = profile.stocks.all().order_by('company')

    if real_entries.exists():
        for entry in real_entries:
            company = entry.company
            curr = DUMMY_CURRENT_PRICES.get(company, DEFAULT_PRICE)
            bought = DUMMY_BOUGHT_AT.get(company, DEFAULT_PRICE - 10)

            holdings.append({
                'company': company,
                'quantity': entry.quantity,
                'current_price': f"${curr:,.2f}",
                'bought_at_price': f"${bought:,.2f}",
            })
    else:
        for company, qty, curr, bought in DUMMY_HOLDINGS:
            holdings.append({
                'company': company,
                'quantity': qty,
                'current_price': f"${curr:,.2f}",
                'bought_at_price': f"${bought:,.2f}",
            })

    return holdings

@login_required
def home_action(request):
    profiles = list(
        Profile.objects.select_related('user').prefetch_related('stocks')
    )

    ranked = [(p, display_net_worth(p)) for p in profiles]
    ranked.sort(key=lambda x: x[1], reverse=True)

    leaderboard = [
        {
            'rank': i + 1,
            'username': p.user.username,
            'net_worth': f"${net:,.2f}",
            'is_current': (p.user == request.user),
        }
        for i, (p, net) in enumerate(ranked)
    ]

    context = {
        'leaderboard': leaderboard
    }
    return render(request, 'alienstocksim/home.html', context)



@login_required
def profile_action(request, username=None):
    if username is None:
        user = request.user
        profile, _ = Profile.objects.get_or_create(user=user)
    else:
        user = get_object_or_404(User, username=username)
        profile = get_object_or_404(Profile, user=user)

    friend_profiles = profile.followers.all().select_related('user').prefetch_related('stocks')

    friends_list = [
        {'username': p.user.username}
        for p in friend_profiles
    ]

    leaderboard_data = [
        {
            'username': p.user.username,
            'net_worth': display_net_worth(p),
        }
        for p in friend_profiles
    ]
    leaderboard_data.sort(key=lambda x: x['net_worth'], reverse=True)

    friends_leaderboard = [
        {
            'username': row['username'],
            'net_worth': f"${row['net_worth']:,.2f}",
        }
        for row in leaderboard_data
    ]

    holdings = build_holdings_for_profile(profile)
    profile_net_worth = display_net_worth(profile)

    context = {
        'profile_user': user,
        'profile': profile,
        'liquid_money': f"${profile.liquid_money:,.2f}",
        'net_worth': f"${profile_net_worth:,.2f}",
        'holdings': holdings,
        'friends_list': friends_list,
        'friends_leaderboard': friends_leaderboard,
        'is_own_profile': (user == request.user),
    }
    return render(request, 'alienstocksim/profile.html', context)


@login_required
def trade_stock(request):
    # Loading/getting data
    data = json.loads(request.body)
    company = data.get("company")
    action = data.get("action")
    price = float(data.get("price"))

    # Creating the stock holding
    profile = request.user.profile
    holding, created = StockEntry.objects.get_or_create(profile=profile, company=company)

    # Different behavior based on action
    if action == "buy":
        if profile.liquid_money < price: 
            return;
        holding.quantity += 1
        profile.liquid_money -= int(data.get("price"))

    elif action == "sell":
        if holding.quantity < 1:
            return;
        holding.quantity -= 1
        profile.liquid_money += int(data.get("price"))

    # Saving the model
    holding.save()
    profile.save()

    # Returning the response to front
    return JsonResponse({
        "quantity": holding.quantity,
        "liquid_money": profile.liquid_money
    })

def stock_stats(request, company):
    # Filters for users who has greater than 0 stock
    holders = StockEntry.objects.filter(company=company, quantity__gt=0)
    # Getting relevant info 
    total_holders = holders.count()
    total_quantity = sum(h.quantity for h in holders)
    # Returning the response to front
    return JsonResponse({
        "holders": total_holders,
        "total_quantity": total_quantity
    })