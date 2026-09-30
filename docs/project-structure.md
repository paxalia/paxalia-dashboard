---

# Project Structure

The security/authentication layer is organized into separate policy, rate-limit, health-diagnostic, WebAuthn, and view
modules:

The v4 security/authentication implementation additionally includes dedicated session-isolation and host-authentication-
bridge modules. The complete tree below is intentionally kept in the README so contributors can see the full package
layout
rather than a reduced feature summary:

```text
paxalia/
├── admin_security.py
├── error_handlers.py
├── security_health.py
├── security_rate_limit.py
├── webauthn_services.py
├── views/
│   ├── auth.py
│   ├── admin_security.py
│   ├── mfa.py
│   └── security.py
├── migrations/
│   └── 0022_paxalia_admin_security.py
└── templates/
    ├── 404.html
    ├── 500.html
    ├── paxalia/
    │   ├── security_overview.html
    │   ├── security_authentication.html
    │   ├── admin_devices.html
    │   └── admin_sessions.html
    └── paxalia_auth/
        ├── login.html
        ├── signup.html
        ├── forgot-password.html
        ├── reset-password.html
        ├── password_change.html
        ├── two-factor.html
        ├── two-factor-setup.html
        ├── recovery-codes.html
        ├── device-register.html
        └── device-verify.html
```

A representative source tree looks like:

```text
paxalia-dashboard/
├── paxalia
│   ├── admin_auth_middleware.py
│   ├── admin_center
│   │   ├── adapter.py
│   │   ├── __init__.py
│   │   ├── package_views.py
│   │   ├── permissions.py
│   │   ├── query.py
│   │   ├── registry.py
│   │   ├── services.py
│   │   ├── urls.py
│   │   ├── utils.py
│   │   └── views.py
│   ├── admin.py
│   ├── admin_security.py
│   ├── alerts.py
│   ├── anomalies.py
│   ├── api_keys.py
│   ├── apps.py
│   ├── auth_middleware.py
│   ├── auth.py
│   ├── bot_classification.py
│   ├── bot_management.py
│   ├── bots_paths.txt
│   ├── chat_ops.py
│   ├── cohorts.py
│   ├── compliance.py
│   ├── conf_uploads.py
│   ├── context_processors.py
│   ├── conversions.py
│   ├── data_import.py
│   ├── error_handlers.py
│   ├── forms.py
│   ├── geoip
│   │   ├── GeoLite2-ASN.mmdb
│   │   ├── GeoLite2-City.mmdb
│   │   └── GeoLite2-Country.mmdb
│   ├── __init__.py
│   ├── locale
│   │   ├── ar
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   ├── en
│   │   │   └── LC_MESSAGES
│   │   │       └── django.po
│   │   ├── es
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   ├── pt-br
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   └── zh-hans
│   │       └── LC_MESSAGES
│   │           ├── django.mo
│   │           └── django.po
│   ├── logging
│   │   ├── application.py
│   │   ├── context.py
│   │   ├── fingerprint.py
│   │   ├── handler.py
│   │   ├── __init__.py
│   │   ├── middleware.py
│   │   ├── redaction.py
│   │   └── services.py
│   ├── management
│   │   └── commands
│   │       ├── aggregate_daily_stats.py
│   │       ├── backfill_pageview_bot_category.py
│   │       ├── backfill_pageview_is_api.py
│   │       ├── check_uptime.py
│   │       ├── cleanup_uploads.py
│   │       ├── create_backup.py
│   │       ├── detect_anomalies.py
│   │       ├── import_bot_paths.py
│   │       ├── paxalia_admin_test.py
│   │       ├── paxalia_availability_check.py
│   │       ├── paxalia_dashboard_test.py
│   │       ├── paxalia_logs_prune.py
│   │       ├── paxalia_logs_test.py
│   │       ├── paxalia_package_inspect.py
│   │       ├── paxalia_package_validate.py
│   │       ├── paxalia_resource_prune.py
│   │       ├── paxalia_server_files_prune.py
│   │       ├── paxalia_transfer_maintenance.py
│   │       ├── prune_analytics_data.py
│   │       ├── prune_security_logs.py
│   │       ├── record_deployment.py
│   │       ├── record_server_metrics.py
│   │       ├── seed_analytics.py
│   │       └── send_scheduled_reports.py
│   ├── middleware.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_security_center.py
│   │   ├── 0003_csp_violations.py
│   │   ├── 0004_pageview_is_api.py
│   │   ├── 0005_flip_anonymize_ip_default.py
│   │   ├── 0006_multisite.py
│   │   ├── 0007_goals_funnels_segments_annotations.py
│   │   ├── 0008_dashboard_access_permissions.py
│   │   ├── 0009_paxalia_api_key.py
│   │   ├── 0010_reporting_sharing.py
│   │   ├── 0011_notifications.py
│   │   ├── 0012_bot_category.py
│   │   ├── 0013_js_error.py
│   │   ├── 0014_uptime_monitoring.py
│   │   ├── 0015_ops_monitoring.py
│   │   ├── 0016_compliance_permission.py
│   │   ├── 0017_data_import.py
│   │   ├── 0018_fix_dailysitestats_duplicates.py
│   │   ├── 0019_sharelink_password_hash.py
│   │   ├── 0020_paxalia_observability.py
│   │   ├── 0021_remove_loginevent_paxalia_log_is_ad_8ef5a0_idx_and_more.py
│   │   ├── 0022_paxalia_admin_security.py
│   │   ├── 0023_server_file_operations.py
│   │   ├── 0024_operations.py
│   │   ├── 0025_reconcile_v500_model_state.py
│   │   ├── 0026_bot_path_management.py
│   │   └── __init__.py
│   ├── models.py
│   ├── packages
│   │   ├── engine.py
│   │   ├── format.py
│   │   ├── __init__.py
│   │   ├── localization.py
│   │   └── security.py
│   ├── permissions.py
│   ├── queue_monitor.py
│   ├── report_delivery.py
│   ├── reporting.py
│   ├── requirements.txt
│   ├── resource_policies.py
│   ├── revenue.py
│   ├── rum.py
│   ├── security_audit.py
│   ├── security_health.py
│   ├── security_rate_limit.py
│   ├── security_scorecard.py
│   ├── segments.py
│   ├── server_files
│   │   ├── audit.py
│   │   ├── exceptions.py
│   │   ├── __init__.py
│   │   ├── middleware.py
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── policy.py
│   │   ├── service.py
│   │   └── views.py
│   ├── settings.py
│   ├── signals.py
│   ├── static
│   │   └── paxalia
│   │       ├── icons
│   │       │   ├── archive
│   │       │   │   ├── icon-file-text.svg
│   │       │   │   ├── icon-global.svg
│   │       │   │   └── icon-time-spendin.svg
│   │       │   ├── brand
│   │       │   │   ├── icon-brand.png
│   │       │   │   └── icon-brand.svg
│   │       │   ├── dependencies.js
│   │       │   ├── realtime.js
│   │       │   ├── sidebar.js
│   │       │   ├── ui
│   │       │   │   ├── icon-bar-chart.svg
│   │       │   │   ├── icon-bot.svg
│   │       │   │   ├── icon-cpu.svg
│   │       │   │   ├── icon-download.svg
│   │       │   │   ├── icon-harddisk.svg
│   │       │   │   ├── icon-key.svg
│   │       │   │   ├── icon-layers.svg
│   │       │   │   ├── icon-memory.svg
│   │       │   │   ├── icon-network.svg
│   │       │   │   ├── icon-overview.svg
│   │       │   │   └── icon-server.svg
│   │       │   └── ui-multi
│   │       │       ├── icon-cloud-uploading.svg
│   │       │       └── icon-setting.svg
│   │       ├── scripts
│   │       │   ├── admin-center.js
│   │       │   ├── admin-overview.js
│   │       │   ├── analytics-events.js
│   │       │   ├── api.js
│   │       │   ├── auth.js
│   │       │   ├── backups.js
│   │       │   ├── billing-chart.js
│   │       │   ├── bot-path-actions.js
│   │       │   ├── bots.js
│   │       │   ├── browser-telemetry.js
│   │       │   ├── chart.umd.js
│   │       │   ├── d3.v3.min.js
│   │       │   ├── datamaps.world.min.js
│   │       │   ├── dependencies.js
│   │       │   ├── error.js
│   │       │   ├── events-chart.js
│   │       │   ├── filter-bar.js
│   │       │   ├── geography-map.js
│   │       │   ├── language-manager.js
│   │       │   ├── logging-filter.js
│   │       │   ├── logs.js
│   │       │   ├── overview.js
│   │       │   ├── page-detail.js
│   │       │   ├── realtime.js
│   │       │   ├── security.js
│   │       │   ├── server
│   │       │   │   ├── cpu.js
│   │       │   │   ├── disk.js
│   │       │   │   ├── memory.js
│   │       │   │   ├── network.js
│   │       │   │   ├── overview.js
│   │       │   │   ├── processes.js
│   │       │   │   └── services.js
│   │       │   ├── server-files.js
│   │       │   ├── sidebar.js
│   │       │   ├── theme-manager.js
│   │       │   ├── topojson.v1.min.js
│   │       │   ├── transfer-center.js
│   │       │   ├── upload-widget.js
│   │       │   └── webauthn.js
│   │       └── styles
│   │           ├── base.css
│   │           ├── components
│   │           │   ├── about.css
│   │           │   ├── admin.css
│   │           │   ├── auth.css
│   │           │   ├── availability.css
│   │           │   ├── backup.css
│   │           │   ├── bot-traffic.css
│   │           │   ├── buttons.css
│   │           │   ├── charts.css
│   │           │   ├── dependencies.css
│   │           │   ├── error.css
│   │           │   ├── export-btn.css
│   │           │   ├── filter-bar.css
│   │           │   ├── icon.css
│   │           │   ├── logging.css
│   │           │   ├── menu.css
│   │           │   ├── notifications.css
│   │           │   ├── release-center.css
│   │           │   ├── rum.css
│   │           │   ├── security.css
│   │           │   ├── server.css
│   │           │   ├── server-files.css
│   │           │   ├── settings-form.css
│   │           │   ├── sidebar.css
│   │           │   ├── stat-cards.css
│   │           │   ├── tables.css
│   │           │   ├── topbar.css
│   │           │   ├── transfer-center.css
│   │           │   ├── typography.css
│   │           │   └── upload.css
│   │           ├── dashboard-refinements.css
│   │           ├── layout.css
│   │           ├── themes.css
│   │           └── tokens.css
│   ├── templates
│   │   ├── 404.html
│   │   ├── 500.html
│   │   ├── paxalia
│   │   │   ├── about.html
│   │   │   ├── admin
│   │   │   │   ├── audit.html
│   │   │   │   ├── bulk_delete.html
│   │   │   │   ├── delete_confirmation.html
│   │   │   │   ├── history.html
│   │   │   │   ├── home.html
│   │   │   │   ├── model_list.html
│   │   │   │   ├── model_localization.html
│   │   │   │   ├── model_overview.html
│   │   │   │   ├── models.html
│   │   │   │   ├── model_stats.html
│   │   │   │   ├── object_detail.html
│   │   │   │   ├── object_form.html
│   │   │   │   ├── package_center.html
│   │   │   │   ├── package_export_center.html
│   │   │   │   ├── package_export.html
│   │   │   │   ├── package_history.html
│   │   │   │   ├── package_import_center.html
│   │   │   │   ├── package_import.html
│   │   │   │   └── package_result.html
│   │   │   ├── admin_devices.html
│   │   │   ├── admin_overview.html
│   │   │   ├── admin_sessions.html
│   │   │   ├── annotations.html
│   │   │   ├── api_docs.html
│   │   │   ├── api.html
│   │   │   ├── api_keys.html
│   │   │   ├── application_logs.html
│   │   │   ├── auth_base.html
│   │   │   ├── backup_reauth.html
│   │   │   ├── backups.html
│   │   │   ├── base.html
│   │   │   ├── billing.html
│   │   │   ├── bots.html
│   │   │   ├── broken_links.html
│   │   │   ├── campaigns.html
│   │   │   ├── cohorts.html
│   │   │   ├── compliance.html
│   │   │   ├── dashboard.html
│   │   │   ├── data_import.html
│   │   │   ├── dependencies.html
│   │   │   ├── email
│   │   │   │   └── report_digest.html
│   │   │   ├── error_base.html
│   │   │   ├── events.html
│   │   │   ├── funnels.html
│   │   │   ├── geography.html
│   │   │   ├── goals.html
│   │   │   ├── includes
│   │   │   │   ├── filter_bar.html
│   │   │   │   └── pagination.html
│   │   │   ├── log_detail.html
│   │   │   ├── login_activity.html
│   │   │   ├── logs.html
│   │   │   ├── mfa_enroll.html
│   │   │   ├── notifications.html
│   │   │   ├── page_detail.html
│   │   │   ├── pages.html
│   │   │   ├── realtime.html
│   │   │   ├── releases.html
│   │   │   ├── reports.html
│   │   │   ├── rum.html
│   │   │   ├── security_admins.html
│   │   │   ├── security_authentication.html
│   │   │   ├── security.html
│   │   │   ├── security_overview.html
│   │   │   ├── segments.html
│   │   │   ├── server_cpu.html
│   │   │   ├── server_deployments.html
│   │   │   ├── server_disk.html
│   │   │   ├── server_files_error.html
│   │   │   ├── server_files_history.html
│   │   │   ├── server_files.html
│   │   │   ├── server_files_preview.html
│   │   │   ├── server_files_reauth.html
│   │   │   ├── server_memory.html
│   │   │   ├── server_network.html
│   │   │   ├── server_overview.html
│   │   │   ├── server_processes.html
│   │   │   ├── server_queues.html
│   │   │   ├── server_services.html
│   │   │   ├── server_slow_queries.html
│   │   │   ├── settings.html
│   │   │   ├── shared_dashboard.html
│   │   │   ├── share_links.html
│   │   │   ├── sites.html
│   │   │   ├── traffic.html
│   │   │   ├── transfer_center.html
│   │   │   └── uptime.html
│   │   └── paxalia_auth
│   │       ├── access-denied.html
│   │       ├── device-register.html
│   │       ├── device-verify.html
│   │       ├── forgot-password.html
│   │       ├── login.html
│   │       ├── password_change_done.html
│   │       ├── password_change.html
│   │       ├── password_reset_complete.html
│   │       ├── password_reset_done.html
│   │       ├── password_reset_email.html
│   │       ├── password_reset_subject.html
│   │       ├── recovery-codes.html
│   │       ├── reset-password.html
│   │       ├── session-expired.html
│   │       ├── signup.html
│   │       ├── two-factor.html
│   │       └── two-factor-setup.html
│   ├── templatetags
│   │   ├── analytics_tags.py
│   │   └── __init__.py
│   ├── test_admin_center.py
│   ├── test_logging.py
│   ├── test_operations.py
│   ├── tests
│   ├── test_security_auth.py
│   ├── test_server_files.py
│   ├── tests.py
│   ├── transfer_center
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── service.py
│   │   └── views.py
│   ├── uptime.py
│   ├── urls.py
│   ├── views
│   │   ├── about.py
│   │   ├── admin_overview.py
│   │   ├── admin_security.py
│   │   ├── annotations.py
│   │   ├── api_docs.py
│   │   ├── api_keys.py
│   │   ├── api.py
│   │   ├── auth.py
│   │   ├── backup.py
│   │   ├── billing.py
│   │   ├── bots.py
│   │   ├── broken_links.py
│   │   ├── campaigns.py
│   │   ├── chat_ops.py
│   │   ├── cohorts.py
│   │   ├── compliance.py
│   │   ├── csp_reports.py
│   │   ├── dashboard.py
│   │   ├── data_import.py
│   │   ├── dependencies.py
│   │   ├── events.py
│   │   ├── export.py
│   │   ├── geography.py
│   │   ├── goals.py
│   │   ├── __init__.py
│   │   ├── login_activity.py
│   │   ├── logs.py
│   │   ├── mfa.py
│   │   ├── notifications.py
│   │   ├── page_detail.py
│   │   ├── pages.py
│   │   ├── paxalia_api.py
│   │   ├── realtime.py
│   │   ├── releases.py
│   │   ├── reports.py
│   │   ├── rum.py
│   │   ├── security.py
│   │   ├── segments.py
│   │   ├── server.py
│   │   ├── settings.py
│   │   ├── share_links.py
│   │   ├── sites.py
│   │   ├── traffic.py
│   │   ├── uploads.py
│   │   ├── uptime.py
│   │   └── utils.py
│   └── webauthn_services.py
├── docs
│   ├── administration.md
│   ├── analytics.md
│   ├── api.md
│   ├── architecture.md
│   ├── authentication.md
│   ├── backup-management.md
│   ├── compliance.md
│   ├── configuration.md
│   ├── contributing.md
│   ├── dashboard.md
│   ├── integrations.md
│   ├── internationalization.md
│   ├── legal.md
│   ├── logging.md
│   ├── monitoring.md
│   ├── operations.md
│   ├── package-format.md
│   ├── project-structure.md
│   ├── releases.md
│   ├── security.md
│   ├── server-files.md
│   ├── themes.md
│   └── transfers.md
├── LICENSE
├── MANIFEST.in
├── pyproject.toml
├── README.md
├── setup.cfg
└── setup.py
```

The `.mmdb` GeoIP database is intentionally excluded from Git because of its size.

---
