from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from alienstocksim.forms import LoginForm, RegisterForm
from alienstocksim.models import Profile, StockEntry

# Create your views here.
def login_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        context['form'] = LoginForm()
        return render(request, 'alienstocksim/login.html', context)

    # Creates a bound form from the request POST parameters
    # And makes the form available in the request context dictionary.
    form = LoginForm(request.POST)

    # Validates the form.
    if not form.is_valid():
        context['form'] = form
        return render(request, 'alienstocksim/login.html', context)

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect('home')


def register_action(request):
    context = {}

    # Just display the registration form if this is a GET request.
    if request.method == 'GET':
        # initialize a new form object (unbound form)
        context['form'] = RegisterForm()
        return render(request, 'alienstocksim/register.html', context)

    # Creates a bound form from the request POST parameters
    # and makes the form available in the request context dictionary
    form = RegisterForm(request.POST)

    # Validates the form.
    if not form.is_valid():
        # the form object has errors built into it
        context['form'] = form
        return render(request, 'alienstocksim/register.html', context)

    # At this point, the form data is valid.  Register and login the user.
    new_user = User.objects.create_user(username=form.cleaned_data['username'],
                                        password=form.cleaned_data['password'],
                                        email=form.cleaned_data['email'],
                                        first_name=form.cleaned_data['first_name'],
                                        last_name=form.cleaned_data['last_name'])

    new_user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])

    login(request, new_user)
    return redirect('home')

@login_required
def logout_action(request):
    logout(request)
    return redirect('login')


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