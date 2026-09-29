"""Typed, safe-to-present errors for Paxalia Server Files."""


class ServerFilesError(Exception):
    """Base error with a stable public code and safe display message."""

    code = "server_files_error"
    public_message = "The filesystem operation could not be completed."
    http_status = 400

    def __init__(self, message=None):
        super().__init__(message or self.public_message)


class ServerFilesDisabled(ServerFilesError):
    code = "disabled"
    public_message = "Paxalia Server Files is disabled."
    http_status = 404


class ServerFilesConfigurationError(ServerFilesError):
    code = "configuration_error"
    public_message = "Paxalia Server Files is not configured safely."
    http_status = 503


class ServerFilesUnsupportedPlatform(ServerFilesError):
    code = "unsupported_platform"
    public_message = "Secure filesystem operations are not supported on this platform."
    http_status = 501


class ServerFilesInvalidPath(ServerFilesError):
    code = "invalid_path"
    public_message = "The requested path is invalid."
    http_status = 400


class ServerFilesDenied(ServerFilesError):
    code = "path_denied"
    public_message = "The requested path is not available."
    http_status = 403


class ServerFilesNotFound(ServerFilesError):
    code = "not_found"
    public_message = "The requested item was not found."
    http_status = 404


class ServerFilesNotDirectory(ServerFilesError):
    code = "not_directory"
    public_message = "The requested item is not a directory."
    http_status = 400


class ServerFilesNotRegularFile(ServerFilesError):
    code = "not_regular_file"
    public_message = "Only regular files are supported for this operation."
    http_status = 400


class ServerFilesAlreadyExists(ServerFilesError):
    code = "already_exists"
    public_message = "An item with that name already exists."
    http_status = 409


class ServerFilesTooLarge(ServerFilesError):
    code = "too_large"
    public_message = "The file exceeds the configured size limit."
    http_status = 413


class ServerFilesUnsupportedPreview(ServerFilesError):
    code = "preview_unsupported"
    public_message = "This file type cannot be previewed."
    http_status = 415


class ServerFilesBinaryFile(ServerFilesError):
    code = "binary_file"
    public_message = "Binary files cannot be previewed."
    http_status = 415


class ServerFilesRateLimited(ServerFilesError):
    code = "rate_limited"
    public_message = "Too many filesystem operations. Please try again shortly."
    http_status = 429


class ServerFilesAuditUnavailable(ServerFilesError):
    code = "audit_unavailable"
    public_message = "The operation was not performed because its audit record could not be created."
    http_status = 503
