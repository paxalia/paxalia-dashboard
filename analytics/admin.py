from django.contrib import admin

from .models import (
    PageView,
    DailySiteStats,
    AnalyticsSettings,
    AnalyticsEvent,
    JSError,
    UptimeMonitor,
    UptimeCheck,
    UptimeIncident,
    ServerMetricSnapshot,
    SlowQuery,
    Deployment,
    FileUpload,
    BackupConfiguration,
    BackupArchive,
    LoginEvent,
    BlockedIP,
    SecurityAuditLog,
    CSPViolation,
    Site,
    Goal,
    Funnel,
    FunnelStep,
    Segment,
    ChartAnnotation,
    PaxaliaAPIKey,
    ScheduledReport,
    ShareLink,
    Notification,
)


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ('path', 'method', 'status_code', 'ip_hash', 'is_bot', 'bot_category', 'created_at')
    list_filter = ('method', 'status_code', 'is_bot', 'bot_category', 'created_at')
    search_fields = ('path', 'ip_hash', 'user_agent')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in PageView._meta.fields]


@admin.register(DailySiteStats)
class DailySiteStatsAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'total_views',
        'unique_ips',
        'api_calls',
        'bot_views',
        'total_sessions',
        'bounces',
    )
    list_filter = ('date',)
    readonly_fields = [f.name for f in DailySiteStats._meta.fields]


@admin.register(AnalyticsSettings)
class AnalyticsSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'anonymize_ip',
        'realtime_refresh_seconds',
        'tracked_paths',
        'bot_paths',
    )

    def has_add_permission(self, request):
        return not AnalyticsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('category', 'action', 'label', 'path', 'created_at', 'country_code')
    list_filter = ('category', 'action', 'created_at', 'country_code')
    search_fields = ('label', 'path', 'session_id')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in AnalyticsEvent._meta.fields]


@admin.register(JSError)
class JSErrorAdmin(admin.ModelAdmin):
    list_display = ('message', 'filename', 'lineno', 'path', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message', 'filename', 'path', 'session_id')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in JSError._meta.fields]


@admin.register(UptimeMonitor)
class UptimeMonitorAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'method', 'expected_status_code', 'check_interval_minutes', 'is_active')
    list_filter = ('is_active', 'method')
    search_fields = ('name', 'url')


@admin.register(UptimeCheck)
class UptimeCheckAdmin(admin.ModelAdmin):
    list_display = ('monitor', 'status', 'status_code', 'response_time_ms', 'checked_at')
    list_filter = ('status', 'checked_at')
    search_fields = ('monitor__name',)
    date_hierarchy = 'checked_at'
    readonly_fields = [f.name for f in UptimeCheck._meta.fields]


@admin.register(UptimeIncident)
class UptimeIncidentAdmin(admin.ModelAdmin):
    list_display = ('monitor', 'started_at', 'resolved_at')
    list_filter = ('started_at',)
    search_fields = ('monitor__name', 'cause')
    date_hierarchy = 'started_at'


@admin.register(ServerMetricSnapshot)
class ServerMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ('recorded_at', 'cpu_percent', 'memory_percent')
    date_hierarchy = 'recorded_at'
    readonly_fields = [f.name for f in ServerMetricSnapshot._meta.fields]


@admin.register(SlowQuery)
class SlowQueryAdmin(admin.ModelAdmin):
    list_display = ('duration_ms', 'path', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('sql', 'path')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in SlowQuery._meta.fields]


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ('version', 'site', 'deployed_at')
    list_filter = ('deployed_at',)
    search_fields = ('version', 'notes')
    date_hierarchy = 'deployed_at'


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename',
        'status',
        'progress_percent',
        'total_size',
        'uploaded_by',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('original_filename',)
    readonly_fields = (
        'id',
        'bytes_received',
        'chunks_received',
        'storage_path',
        'created_at',
        'updated_at',
        'completed_at',
    )


@admin.register(BackupConfiguration)
class BackupConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'enabled',
        'schedule',
        'retention_count',
        'storage_path',
        'updated_at',
    )
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        return not BackupConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BackupArchive)
class BackupArchiveAdmin(admin.ModelAdmin):
    list_display = ('filename', 'size', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('filename', 'error_message')
    readonly_fields = [f.name for f in BackupArchive._meta.fields]


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'user', 'username_attempted', 'result',
        'ip_address', 'country_name', 'browser', 'os', 'is_new_location',
    )
    list_filter = ('result', 'is_new_location', 'created_at')
    search_fields = ('username_attempted', 'ip_address', 'user__username')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in LoginEvent._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'active', 'reason', 'created_by', 'created_at')
    list_filter = ('active',)
    search_fields = ('ip_address', 'reason')


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('action', 'detail', 'user__username')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in SecurityAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(CSPViolation)
class CSPViolationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'violated_directive', 'blocked_uri', 'document_uri')
    list_filter = ('violated_directive', 'created_at')
    search_fields = ('blocked_uri', 'document_uri', 'source_file')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in CSPViolation._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'domain')


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'goal_type', 'match_value', 'site', 'is_active', 'created_at')
    list_filter = ('goal_type', 'is_active')
    search_fields = ('name', 'match_value')


class FunnelStepInline(admin.TabularInline):
    model = FunnelStep
    extra = 1


@admin.register(Funnel)
class FunnelAdmin(admin.ModelAdmin):
    list_display = ('name', 'site', 'created_at')
    inlines = [FunnelStepInline]


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'site', 'created_at')
    search_fields = ('name',)


@admin.register(ChartAnnotation)
class ChartAnnotationAdmin(admin.ModelAdmin):
    list_display = ('date', 'label', 'site', 'created_by')
    list_filter = ('date',)
    search_fields = ('label',)


@admin.register(PaxaliaAPIKey)
class PaxaliaAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key_prefix', 'site', 'scope_ingest', 'scope_read', 'is_active', 'last_used_at')
    list_filter = ('is_active', 'scope_ingest', 'scope_read')
    search_fields = ('name', 'key_prefix')
    readonly_fields = ('key_prefix', 'key_hash', 'created_at', 'last_used_at')


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'frequency', 'site', 'is_active', 'last_sent_at')
    list_filter = ('frequency', 'is_active')
    search_fields = ('name', 'recipient_emails')


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'site', 'has_password', 'is_active', 'expires_at', 'last_viewed_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('password_hash', 'created_at', 'last_viewed_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'category', 'subject', 'site', 'is_read')
    list_filter = ('category', 'is_read')
    search_fields = ('subject', 'message')
    readonly_fields = ('created_at',)
