from django.contrib import admin
from .models import PageView, DailySiteStats, AnalyticsSettings


# Register your models here.


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ('path', 'method', 'status_code', 'ip_hash', 'created_at')
    list_filter = ('method', 'status_code', 'created_at')
    search_fields = ('path',)
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in PageView._meta.fields]


@admin.register(DailySiteStats)
class DailySiteStatsAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_views', 'unique_ips', 'api_calls')
    readonly_fields = [f.name for f in DailySiteStats._meta.fields]


@admin.register(AnalyticsSettings)
class AnalyticsSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Only allow one instance
        return not AnalyticsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
