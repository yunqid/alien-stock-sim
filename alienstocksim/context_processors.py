from alienstocksim.models import DirectMessage


def dm_unread(request):
    """Expose unread direct-message counts for nav badge (recipient-only)."""
    if not request.user.is_authenticated:
        return {
            "has_unread_dm": False,
            "unread_dm_count": 0,
        }
    n = DirectMessage.objects.filter(
        recipient=request.user,
        read_at__isnull=True,
    ).count()
    return {
        "has_unread_dm": n > 0,
        "unread_dm_count": n,
    }
