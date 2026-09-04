from django.contrib import admin

from .models import (
    PageView,
    DailySiteStats,
    AnalyticsSettings,
    AnalyticsEvent,
    FileUpload,
    BackupConfiguration,
    BackupArchive,
    LoginEvent,
    BlockedIP,
    SecurityAuditLog,
    CSPViolation,
)


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ('path', 'method', 'status_code', 'ip_hash', 'is_bot', 'created_at')
    list_filter = ('method', 'status_code', 'is_bot', 'created_at')
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
