from django.contrib import admin
from alienstocksim.models import DirectMessage


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "created_at", "read_at", "body_preview")
    list_filter = ("created_at",)
    search_fields = ("sender__username", "recipient__username", "body")
    ordering = ("-created_at",)

    @staticmethod
    def body_preview(obj):
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body
