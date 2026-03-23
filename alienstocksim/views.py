from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from alienstocksim.forms import LoginForm, RegisterForm
from alienstocksim.models import Profile, StockEntry
from alienstocksim.pricing import get_last_price
import json
from django.http import JsonResponse
from google import genai
from google.genai import types


client = genai.Client()

def landing_action(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'alienstocksim/landing.html')


def generate_headline_batch():
    companies = ["Googlin", "Pear", "BenefitCo", "Fire Rage Inc."]
    
    prompt = f"""
    You are a financial headline generator for a fake stock trading game.
    Generate a JSON list of EXACTLY 10 fictional news events. 
    
    For each event, randomly pick one of these companies: {', '.join(companies)}.
    For each event, randomly assign a severity level of 1, 2, or 3 (3 is most impactful, 1 is least).
    
    The headline should reference the company and hint at whether its stock will go up or down based on the severity. 
    NOTE: Severity is not indicative of good or bad. Severity 3 can be very good or very bad.
    
    Respond ONLY with a valid JSON array of objects in this exact format:
    [
        {{
            "company": "Company Name",
            "headline": "The headline text here",
            "blurb": "The short story blurb here.",
            "direction": "up" or "down",
            "severity": "1", "2", or "3"
        }}
    ]
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=prompt,
        config=types.GenerateContentConfig(
            # forces the API to return pure JSON
            response_mime_type="application/json",
        )
    )
    
    return json.loads(response.text)


# Helper functions

def net_worth_live(profile):
    """
    Net worth from DB: liquid_money + sum(quantity * cached live price) per position.
    Used for profile summary and all leaderboards (no dummy portfolio).
    """
    total = profile.liquid_money
    for entry in profile.stocks.filter(quantity__gt=0):
        total += entry.quantity * get_last_price(entry.company)
    return total


def build_holdings_for_profile(profile):
    """Holdings table: only DB rows with quantity > 0; prices from cache / cost basis from trades."""
    holdings = []
    for entry in profile.stocks.filter(quantity__gt=0).order_by('company'):
        curr = get_last_price(entry.company)
        if entry.cost_basis_paid > 0:
            avg_buy = entry.cost_basis_paid / entry.quantity
            bought_display = f"${avg_buy:,.2f}"
        else:
            bought_display = "—"

        holdings.append({
            'company': entry.company,
            'quantity': entry.quantity,
            'current_price': f"${curr:,.2f}",
            'bought_at_price': bought_display,
        })

    return holdings


def _friends_leaderboard_rows(profile, highlight_profile):
    """
    Rank the profile owner and everyone they follow by net worth.
    highlight_profile is used to mark the row for the profile page being viewed.
    """
    participants = list(
        profile.following.select_related('user').prefetch_related('stocks')
    )
    seen = {p.pk for p in participants}
    if profile.pk not in seen:
        participants.append(profile)

    ranked = [(p, net_worth_live(p)) for p in participants]
    ranked.sort(key=lambda x: x[1], reverse=True)

    return [
        {
            'rank': i + 1,
            'username': p.user.username,
            'net_worth': f"${net:,.2f}",
            'is_highlight': (p.pk == highlight_profile.pk),
        }
        for i, (p, net) in enumerate(ranked)
    ]


@login_required
def home_action(request):
    profiles = list(
        Profile.objects.select_related('user').prefetch_related('stocks')
    )

    ranked = [(p, net_worth_live(p)) for p in profiles]
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

    viewer_profile, _ = Profile.objects.get_or_create(user=request.user)
    is_own_profile = user == request.user
    is_following = profile.followers.filter(pk=viewer_profile.pk).exists()

    followers_qs = profile.followers.select_related('user').prefetch_related('stocks')
    followers_list = [{'username': p.user.username} for p in followers_qs]

    following_qs = profile.following.select_related('user').prefetch_related('stocks')
    following_list = [{'username': p.user.username} for p in following_qs]

    friends_leaderboard = _friends_leaderboard_rows(profile, highlight_profile=profile)

    search_query = (request.GET.get('q') or '').strip()
    search_results = []
    if is_own_profile and search_query:
        search_results = list(
            User.objects.filter(username__icontains=search_query)
            .exclude(pk=request.user.pk)
            .order_by('username')[:20]
        )

    holdings = build_holdings_for_profile(profile)
    profile_net_worth = net_worth_live(profile)

    context = {
        'profile_user': user,
        'profile': profile,
        'liquid_money': f"${profile.liquid_money:,.2f}",
        'net_worth': f"${profile_net_worth:,.2f}",
        'holdings': holdings,
        'followers_list': followers_list,
        'following_list': following_list,
        'friends_leaderboard': friends_leaderboard,
        'is_own_profile': is_own_profile,
        'is_following': is_following,
        'search_query': search_query,
        'search_results': search_results,
    }
    return render(request, 'alienstocksim/profile.html', context)


@login_required
@require_POST
def follow_toggle(request):
    username = (request.POST.get('username') or '').strip()
    action = request.POST.get('action')
    next_url = request.POST.get('next') or reverse('home')

    if not username or username == request.user.username:
        return redirect(next_url)

    target_user = get_object_or_404(User, username=username)
    target_profile = get_object_or_404(Profile, user=target_user)
    me, _ = Profile.objects.get_or_create(user=request.user)

    if action == 'follow':
        target_profile.followers.add(me)
    elif action == 'unfollow':
        target_profile.followers.remove(me)

    return redirect(next_url)


@login_required
def trade_stock(request):
    # Loading/getting data
    data = json.loads(request.body)
    company = data.get("company")
    action = data.get("action")
    price = float(data.get("price"))
    price_int = int(data.get("price"))

    # Creating the stock holding
    profile = request.user.profile
    holding, created = StockEntry.objects.get_or_create(profile=profile, company=company)

    # Different behavior based on action
    if action == "buy":
        if profile.liquid_money < price_int:
            return JsonResponse({"error": "insufficient_funds"}, status=400)
        holding.quantity += 1
        holding.cost_basis_paid += price_int
        profile.liquid_money -= price_int

    elif action == "sell":
        if holding.quantity < 1:
            return JsonResponse({"error": "no_shares"}, status=400)
        if holding.quantity == 1:
            holding.cost_basis_paid = 0
        else:
            holding.cost_basis_paid -= holding.cost_basis_paid // holding.quantity
        holding.quantity -= 1
        profile.liquid_money += price_int

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