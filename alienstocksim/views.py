from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from alienstocksim.models import DirectMessage, Profile, StockEntry, PriceCache
from alienstocksim.pricing import get_last_price
import json
import os
from django.http import JsonResponse, FileResponse
from google import genai
from google.genai import types
from django.conf import settings
import time
from django.db.utils import OperationalError


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


def serve_sw(request):
    path = os.path.join(settings.BASE_DIR, 'sw.js')
    response = FileResponse(open(path, 'rb'), content_type = 'application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response


@login_required
def unread_message_count(request):
    latest = (
        DirectMessage.objects.filter(recipient=request.user, read_at__isnull=True)
        .select_related("sender")
        .order_by("-created_at")
        .first()
    )
    count = DirectMessage.objects.filter(
        recipient=request.user, read_at__isnull=True
    ).count()

    return JsonResponse({
        "unread_count": count,
        "sender": latest.sender.username if latest else None,
        "preview": latest.body[:80] if latest else None,
        "thread_url": reverse("messages_thread", args=[latest.sender.username]) if latest else None,
    })

def _profiles_mutual(a: Profile, b: Profile) -> bool:
    """True if each follows the other (and they are not the same account)."""
    if a.pk == b.pk:
        return False
    return b.followers.filter(pk=a.pk).exists() and a.followers.filter(pk=b.pk).exists()


def _mutual_friends_qs(profile: Profile):
    """Profiles I follow who also follow me."""
    return profile.following.filter(followers=profile).select_related("user").order_by(
        "user__username"
    )


def net_worth_live(profile):
    """
    Net worth from DB: liquid_money + sum(quantity * cached live price) per position.
    Used for profile summary and all leaderboards (no dummy portfolio).
    """
    total = profile.liquid_money
    for entry in profile.stocks.filter(quantity__gt=0):
        total += entry.quantity * get_last_price(entry.company)
    return total


def _global_leaderboard_rows(for_user):
    """Global ranking by live net worth; marks the requesting user's row."""
    profiles = list(
        Profile.objects.select_related("user").prefetch_related("stocks")
    )
    ranked = [(p, net_worth_live(p)) for p in profiles]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [
        {
            "rank": i + 1,
            "username": p.user.username,
            "net_worth": f"${net:,.2f}",
            "is_current": (p.user == for_user),
        }
        for i, (p, net) in enumerate(ranked)
    ]


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
    # Ensure this user has a Profile row so they appear on first visit (not only after /profile).
    Profile.objects.get_or_create(user=request.user)
    context = {"leaderboard": _global_leaderboard_rows(request.user)}
    return render(request, "alienstocksim/home.html", context)


@login_required
def leaderboard_api(request):
    """JSON for home sidebar: same ordering as server-rendered leaderboard."""
    Profile.objects.get_or_create(user=request.user)
    return JsonResponse({"rows": _global_leaderboard_rows(request.user)})



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
    is_mutual = (
        not is_own_profile and _profiles_mutual(viewer_profile, profile)
    )

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
        'is_mutual': is_mutual,
        'search_query': search_query,
        'search_results': search_results,
    }
    return render(request, 'alienstocksim/profile.html', context)


def _safe_redirect_url(request, candidate: str, fallback: str) -> str:
    """Block open redirects: same-site relative paths or full URLs on this host only."""
    if not candidate:
        return fallback
    c = candidate.strip()
    if c.startswith("/") and not c.startswith("//"):
        return c
    if url_has_allowed_host_and_scheme(
        c,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return c
    return fallback


@login_required
@require_POST
def follow_toggle(request):
    username = (request.POST.get('username') or '').strip()
    action = request.POST.get('action')
    fallback = reverse('home')
    next_url = _safe_redirect_url(
        request, (request.POST.get('next') or '').strip(), fallback
    )

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
def messages_inbox(request):
    me, _ = Profile.objects.get_or_create(user=request.user)
    mutual = list(_mutual_friends_qs(me))
    thread_rows = []
    for p in mutual:
        u = p.user
        last = (
            DirectMessage.objects.filter(
                Q(sender=request.user, recipient=u) | Q(sender=u, recipient=request.user)
            )
            .order_by("-created_at")
            .first()
        )
        unread_count = DirectMessage.objects.filter(
            sender=u, recipient=request.user, read_at__isnull=True
        ).count()
        thread_rows.append(
            {
                "username": u.username,
                "last_preview": (last.body[:100] + "…")
                if last and len(last.body) > 100
                else (last.body if last else ""),
                "last_at": last.created_at if last else None,
                "unread_count": unread_count,
            }
        )
    with_time = [r for r in thread_rows if r["last_at"]]
    no_time = [r for r in thread_rows if not r["last_at"]]
    with_time.sort(key=lambda r: r["last_at"], reverse=True)
    thread_rows = with_time + no_time

    context = {"thread_rows": thread_rows}
    return render(request, "alienstocksim/messages_inbox.html", context)


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def messages_thread(request, username):
    other = get_object_or_404(User, username=username)
    if other.pk == request.user.pk:
        return redirect("messages_inbox")

    me_profile, _ = Profile.objects.get_or_create(user=request.user)
    other_profile = get_object_or_404(Profile, user=other)

    if not _profiles_mutual(me_profile, other_profile):
        django_messages.error(
            request,
            "You can only message players who follow you back (mutual followers).",
        )
        return redirect("messages_inbox")

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if not body:
            django_messages.warning(request, "Message cannot be empty.")
        elif len(body) > 5000:
            django_messages.error(request, "Message is too long.")
        else:
            DirectMessage.objects.create(
                sender=request.user,
                recipient=other,
                body=body,
            )
            django_messages.success(request, "Message sent.")
        return redirect(reverse("messages_thread", args=[username]))

    # Mark messages from this sender as read now that the recipient opened the thread.
    DirectMessage.objects.filter(
        recipient=request.user,
        sender=other,
        read_at__isnull=True,
    ).update(read_at=timezone.now())

    qs = (
        DirectMessage.objects.filter(
            Q(sender=request.user, recipient=other)
            | Q(sender=other, recipient=request.user)
        )
        .select_related("sender", "recipient")
        .order_by("created_at")
    )

    context = {
        "other_user": other,
        "messages_list": list(qs),
    }
    return render(request, "alienstocksim/messages_thread.html", context)

@login_required
def messages_thread_poll(request, username):
    other = get_object_or_404(User, username=username)
    if other.pk == request.user.pk:
        return JsonResponse({"error": "invalid"}, status=400)

    my_profile, _ = Profile.objects.get_or_create(user=request.user)
    other_profile = get_object_or_404(Profile, user=other)

    if not _profiles_mutual(my_profile, other_profile):
        return JsonResponse({"error": "not_mutual"}, status=403)

    after_id = request.GET.get("after_id")
    qs = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other)
        | Q(sender=other, recipient=request.user)
    ).select_related("sender").order_by("created_at")

    if after_id:
        qs = qs.filter(pk__gt=after_id)

    qs.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())

    messages_out = [
        {
            "id": m.pk,
            "body": m.body,
            "sender": m.sender.username,
            "created_at": m.created_at.strftime("%b %d, %Y, %I:%M %p"),
            "is_mine": m.sender == request.user,
        }
        for m in qs
    ]

    return JsonResponse({"messages": messages_out})


# Handels all requests regading trading of stocks
@login_required
@require_POST
def trade_stock(request):
    """
    Execute one share buy/sell for the authenticated user only.
    Uses select_for_update + atomic to prevent race conditions on balance and quantity.
    """
    try:
        data = json.loads(request.body.decode("utf-8") if request.body else "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    # Getting some basic information regarding the transaction
    company = (data.get("company") or "").strip()
    if not company or len(company) > 200:
        return JsonResponse({"error": "invalid_company"}, status=400)

    action = data.get("action")
    if action not in ("buy", "sell"):
        return JsonResponse({"error": "invalid_action"}, status=400)

    raw_price = data.get("price")
    try:
        price = float(raw_price)
        price_int = int(raw_price)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_price"}, status=400)

    if price_int <= 0 or price < 0:
        return JsonResponse({"error": "invalid_price"}, status=400)
    
    amount = data.get("amount")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_amount"}, status=400)
    
    if amount < 0:
        return JsonResponse({"error": "invalid_amount"}, status=400)
    
    # Tries the transaction up to 5 times before failing
    for attempt in range(5):
        try:
            with transaction.atomic():
                # Make sure that profile and cache exists
                # Also locks them
                Profile.objects.get_or_create(user=request.user)
                profile = Profile.objects.select_for_update().get(user=request.user)
                cache = PriceCache.objects.select_for_update().filter(company=company).first()

                # Getting the stock entry
                StockEntry.objects.get_or_create(
                    profile=profile,
                    company=company,
                    defaults={"quantity": 0, "cost_basis_paid": 0},
                )
                holding = StockEntry.objects.select_for_update().get(
                    profile=profile, 
                    company=company,
                )
                
                remaining = cache.remaining if cache else 1000 # Defaults to 1000

                # Dealing with the buy/sell actions
                if action == "buy":
                    if remaining < amount:
                        return JsonResponse({"error": "no_shares_available"}, status=400)
                    if profile.liquid_money < price_int * amount:
                        return JsonResponse({"error": "insufficient_funds"}, status=400)
                    holding.quantity += amount
                    holding.cost_basis_paid += price_int * amount
                    profile.liquid_money -= price_int * amount
                    if cache:
                        cache.remaining -= amount
                        cache.save()
                else: 
                    if holding.quantity < amount:
                        return JsonResponse({"error": "no_shares"}, status=400)
                    if holding.quantity == amount:
                        holding.cost_basis_paid = 0
                    else:
                        holding.cost_basis_paid -= holding.cost_basis_paid // holding.quantity * amount
                    holding.quantity -= amount
                    profile.liquid_money += price_int * amount
                    if cache:
                        cache.remaining += amount
                        cache.save()

                holding.save()
                profile.save()

        # Tries the transaction multiple times
        # This only happens if the database is locked
        except OperationalError as e:
            if attempt < 4:
                time.sleep(0.3) 
                continue
            return JsonResponse({"error": "server_error"}, status=500)

        except Profile.DoesNotExist:
            return JsonResponse({"error": "no_profile"}, status=400)
        
        except Exception as e:
            return JsonResponse({"error": "server_error"}, status=500)

        return JsonResponse(
            {
                "quantity": holding.quantity,
                "liquid_money": profile.liquid_money,
            }
        )

# Returns information regarding the stock specifically
@login_required
def stock_stats(request, company):
    company = (company or "").strip()
    if not company or len(company) > 200:
        return JsonResponse({"error": "invalid_company"}, status=400)

    holders = StockEntry.objects.filter(company=company, quantity__gt=0)
    # Getting relevant info 
    total_holders = holders.count()
    total_quantity = sum(h.quantity for h in holders)
    # Getting the amount of shares left
    cache = PriceCache.objects.filter(company=company).first()
    shares_remaining = cache.remaining if cache else 1000
    # Returning the response to front
    return JsonResponse({
        "holders": total_holders,
        "total_quantity": total_quantity,
        "shares_remaining": shares_remaining,
    })

# Returns information regarding the user specifically
@login_required
def user_stats(request, company):
    company = (company or "").strip()
    if not company or len(company) > 200:
        return JsonResponse({"error": "invalid_company"}, status=400)

    # Getting the current user
    profile, _ = Profile.objects.get_or_create(user=request.user)
    # Getting the amount of the current stock held by the user
    holding = StockEntry.objects.filter(profile=profile, company=company).first()
    quantity = holding.quantity if holding else 0
    # Getting the price of the company
    price = get_last_price(company)

    return JsonResponse({
        "quantity": quantity,
        "liquid_money": profile.liquid_money,
        "price": price,
    })