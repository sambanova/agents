"""
Sandbox security module — defense-in-depth for Daytona sandbox execution.

Provides input validation (command blocklist, pip package sanitization, filename validation),
output redaction (detect-secrets + infrastructure patterns), and structured security logging.
"""

import re
from typing import List, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 1a. Shell command validation
# ---------------------------------------------------------------------------

# Commands that are always blocked (network recon, credential exfil, reverse shells)
_BLOCKED_COMMANDS = [
    # Network reconnaissance
    "nmap", "masscan", "nslookup", "dig", "host", "netstat",
    "ifconfig", "traceroute", "tracepath", "mtr",
    # Reverse shell / tunneling
    "ncat", "socat", "telnet",
]

# Patterns that need regex matching (context-sensitive blocks)
_BLOCKED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # ss with flags that enumerate sockets
    (re.compile(r"\bss\s+-"), "socket enumeration (ss) is not permitted"),
    # ip addr / ip route / ip neigh
    (re.compile(r"\bip\s+(addr|route|neigh|link|a|r|n)\b"), "ip network commands are not permitted"),
    # arp
    (re.compile(r"\barp\b"), "arp is not permitted"),
    # Bare `env` (but NOT `env python`, `env bash`, etc.)
    (re.compile(r"(?:^|\s|;|&&|\|)\benv\s*$"), "bare 'env' dumps credentials — use specific variables instead"),
    (re.compile(r"(?:^|\s|;|&&|\|)\benv\s*[|;>&]"), "piping env output is not permitted"),
    # printenv
    (re.compile(r"\bprintenv\b"), "printenv dumps credentials and is not permitted"),
    # /proc access
    (re.compile(r"/proc/self/(environ|maps|cmdline)"), "accessing /proc/self is not permitted"),
    # Credential files
    (re.compile(r"\bcat\s+/etc/(passwd|shadow)"), "reading system credential files is not permitted"),
    (re.compile(r"\bcat\s+[^\s]*\.(env|pem|key)\b"), "reading credential/key files is not permitted"),
    # Shell variable expansion for secrets
    (re.compile(r"\$\{?(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|AWS_SECRET|DATABASE_URL)\b"),
     "expanding secret environment variables is not permitted"),
    # nc with listen/exec flags (reverse shell)
    (re.compile(r"\bnc\s+.*(-[lep]|--listen|--exec)\b"), "netcat with listen/exec flags is not permitted"),
    (re.compile(r"\bnc\s+-"), "netcat is not permitted in the sandbox"),
    # /dev/tcp (bash reverse shell)
    (re.compile(r"/dev/tcp/"), "/dev/tcp reverse shells are not permitted"),
    # ssh reverse tunnel
    (re.compile(r"\bssh\s+.*-R\b"), "SSH reverse tunnels are not permitted"),
    # curl/wget to private IPs or metadata endpoints
    (re.compile(
        r"\b(curl|wget)\s+[^\s]*"
        r"(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"|169\.254\.\d{1,3}\.\d{1,3}"
        r"|metadata\.google\.internal"
        r"|169\.254\.169\.254)"
    ), "network requests to private/internal IPs are not permitted"),
]


def validate_shell_command(command: str) -> Tuple[bool, str]:
    """
    Validate a shell command against the blocklist.

    Returns:
        (True, "") if command is allowed.
        (False, reason) if command is blocked.
    """
    if not command or not command.strip():
        return False, "empty command"

    cmd_lower = command.strip().lower()

    # Check simple blocked commands (word boundary match)
    for blocked in _BLOCKED_COMMANDS:
        # Match as first token or after shell operators
        if re.search(rf"(?:^|[;|&\s]){re.escape(blocked)}(?:\s|$|;|&|\|)", cmd_lower):
            return False, f"'{blocked}' is not permitted in the sandbox"

    # Check regex patterns
    for pattern, reason in _BLOCKED_PATTERNS:
        if pattern.search(command):
            return False, reason

    return True, ""


# ---------------------------------------------------------------------------
# 1b. Pip package validation
# ---------------------------------------------------------------------------

# Allowed pattern: package name with optional extras and version spec
_PIP_PACKAGE_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(\[[a-zA-Z0-9,._-]+\])?(([><=!~]=?|===?)[a-zA-Z0-9.*+!_-]+)*$"
)

# Characters that indicate shell injection in a package name
_SHELL_METACHARACTERS = set(";|&`$(){}!><\n\r")


def validate_pip_package(package: str) -> Tuple[bool, str]:
    """
    Validate a pip package specification.

    Returns:
        (True, "") if the package name is safe.
        (False, reason) if it contains suspicious characters.
    """
    if not package or not package.strip():
        return False, "empty package name"

    package = package.strip()

    # Check for shell metacharacters first (fast path)
    bad_chars = _SHELL_METACHARACTERS.intersection(package)
    if bad_chars:
        return False, f"package name contains shell metacharacters: {bad_chars}"

    # Validate against expected pattern
    if not _PIP_PACKAGE_PATTERN.match(package):
        return False, f"package name '{package}' does not match expected format"

    return True, ""


def sanitize_pip_packages(packages_str: str) -> Tuple[List[str], List[str]]:
    """
    Validate a space-separated string of pip packages.

    Returns:
        (valid_packages, errors) where errors contains descriptions of rejected packages.
    """
    if not packages_str or not packages_str.strip():
        return [], ["no packages specified"]

    valid = []
    errors = []

    for pkg in packages_str.split():
        pkg = pkg.strip()
        if not pkg:
            continue
        ok, reason = validate_pip_package(pkg)
        if ok:
            valid.append(pkg)
        else:
            errors.append(f"rejected '{pkg}': {reason}")
            log_security_event(
                "pip_package_rejected",
                "warning",
                package=pkg,
                reason=reason,
            )

    return valid, errors


# ---------------------------------------------------------------------------
# 1c. Filename validation
# ---------------------------------------------------------------------------

_FILENAME_DANGEROUS_CHARS = set('"\'\\`\n\r\0')


def validate_filename(filename: str) -> Tuple[bool, str]:
    """
    Validate a filename for path traversal and injection characters.

    Returns:
        (True, "") if safe.
        (False, reason) if dangerous.
    """
    if not filename or not filename.strip():
        return False, "empty filename"

    # Path traversal
    if ".." in filename:
        return False, "path traversal ('..') is not permitted in filenames"

    # Characters that could escape string interpolation in generated Python code
    bad_chars = _FILENAME_DANGEROUS_CHARS.intersection(filename)
    if bad_chars:
        readable = {"\n": "\\n", "\r": "\\r", "\0": "\\0"}
        display = ", ".join(readable.get(c, repr(c)) for c in bad_chars)
        return False, f"filename contains dangerous characters: {display}"

    return True, ""


# ---------------------------------------------------------------------------
# 1d. Output redaction
# ---------------------------------------------------------------------------

# Infrastructure patterns that detect-secrets doesn't cover
_PRIVATE_IP_PATTERN = re.compile(
    r"\b("
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3}"
    r")\b"
)

_INTERNAL_DNS_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._-]+\.(svc\.cluster\.local|internal)\b"
)

_CONNECTION_STRING_PATTERN = re.compile(
    r"(redis|postgresql|postgres|mysql|mongodb|amqp)://[^\s\"'<>]+"
)

# Env var dump detection: multiple lines matching KEY=value pattern
_ENV_LINE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+=.+$", re.MULTILINE)


def _redact_with_detect_secrets(text: str) -> str:
    """Use detect-secrets library to find and redact credentials in text."""
    try:
        from detect_secrets.core.scan import scan_line
        from detect_secrets.settings import transient_settings

        with transient_settings({"plugins_used": [
            {"name": "ArtifactoryDetector"},
            {"name": "AWSKeyDetector"},
            {"name": "AzureStorageKeyDetector"},
            {"name": "BasicAuthDetector"},
            {"name": "CloudantDetector"},
            {"name": "DiscordBotTokenDetector"},
            {"name": "GitHubTokenDetector"},
            {"name": "IbmCloudIamDetector"},
            {"name": "IbmCosHmacDetector"},
            {"name": "JwtTokenDetector"},
            {"name": "MailchimpDetector"},
            {"name": "NpmDetector"},
            {"name": "SendGridDetector"},
            {"name": "SlackDetector"},
            {"name": "SoftlayerDetector"},
            {"name": "SquareOAuthDetector"},
            {"name": "StripeDetector"},
            {"name": "TwilioKeyDetector"},
        ]}):
            lines = text.split("\n")
            redacted_lines = []
            for line in lines:
                secrets = scan_line(line)
                if secrets:
                    for secret in secrets:
                        secret_value = secret.secret_value
                        if secret_value and secret_value in line:
                            line = line.replace(secret_value, "[REDACTED_SECRET]")
                            log_security_event(
                                "secret_redacted",
                                "warning",
                                secret_type=secret.type,
                            )
                redacted_lines.append(line)
            return "\n".join(redacted_lines)
    except ImportError:
        logger.warning("detect-secrets not installed, skipping secret detection")
        return text
    except Exception as e:
        logger.warning("detect-secrets scanning failed, skipping", error=str(e))
        return text


def _redact_infrastructure_patterns(text: str) -> str:
    """Redact private IPs, internal DNS, and connection strings."""
    # Private IPs
    text = _PRIVATE_IP_PATTERN.sub("[REDACTED_IP]", text)

    # Internal DNS names
    text = _INTERNAL_DNS_PATTERN.sub("[REDACTED_INTERNAL_HOST]", text)

    # Connection strings
    text = _CONNECTION_STRING_PATTERN.sub("[REDACTED_CONNECTION_STRING]", text)

    # Env var dump detection: if 5+ consecutive KEY=value lines, redact them
    lines = text.split("\n")
    redacted_lines = []
    env_run = []

    for line in lines:
        if _ENV_LINE_PATTERN.match(line):
            env_run.append(line)
        else:
            if len(env_run) >= 5:
                # This looks like env/printenv output — redact the whole block
                redacted_lines.append(
                    f"[REDACTED_ENV_DUMP — {len(env_run)} environment variables hidden]"
                )
                log_security_event(
                    "env_dump_redacted",
                    "warning",
                    lines_redacted=len(env_run),
                )
            else:
                redacted_lines.extend(env_run)
            env_run = []
            redacted_lines.append(line)

    # Handle trailing env run
    if len(env_run) >= 5:
        redacted_lines.append(
            f"[REDACTED_ENV_DUMP — {len(env_run)} environment variables hidden]"
        )
        log_security_event(
            "env_dump_redacted",
            "warning",
            lines_redacted=len(env_run),
        )
    else:
        redacted_lines.extend(env_run)

    return "\n".join(redacted_lines)


def redact_sensitive_output(output: str) -> str:
    """
    Two-layer output redaction:
    1. detect-secrets for credentials/tokens
    2. Custom regex for infrastructure patterns
    """
    if not output:
        return output

    # Layer 1: detect-secrets
    output = _redact_with_detect_secrets(output)

    # Layer 2: Infrastructure patterns
    output = _redact_infrastructure_patterns(output)

    return output


# ---------------------------------------------------------------------------
# 1e. Structured security logging
# ---------------------------------------------------------------------------


def log_security_event(event_type: str, severity: str, **kwargs):
    """
    Emit a structured security log event.

    Args:
        event_type: e.g. "command_blocked", "secret_redacted", "pip_package_rejected"
        severity: "info", "warning", "error"
        **kwargs: Additional context fields
    """
    log_fn = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }.get(severity, logger.info)

    log_fn(
        "security_event",
        security_event=True,
        event_type=event_type,
        severity=severity,
        **kwargs,
    )
