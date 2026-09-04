"""
WebZFS Settings Views
Provides the settings page for theme selection, session timeout configuration,
backup and restore of WebZFS configuration, and other WebZFS configuration.
"""
import io
import logging
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from config.templates import templates
from services.theme import (
    get_active_theme,
    get_all_themes_for_template,
    get_theme_variables,
    save_theme,
    is_valid_theme,
    THEME_REGISTRY,
)
from services.corner_style import (
    get_active_corner_style,
    get_all_corner_styles_for_template,
    save_corner_style,
    is_valid_corner_style,
    CORNER_STYLE_DISPLAY_NAMES,
)
from services.timeout_settings import (
    get_effective_session_timeout,
    save_session_timeout,
    reset_session_timeout,
    format_timeout_display,
    DEFAULT_SESSION_TIMEOUT,
    SESSION_TIMEOUT_PRESETS,
    VALID_TIMEOUT_VALUES,
)
from services import backup_restore
from auth.dependencies import get_current_user


logger = logging.getLogger(__name__)


# Maximum size accepted for an uploaded backup archive (8 MB is generous;
# real archives are typically a few KB to tens of KB).
MAX_UPLOAD_SIZE = 8 * 1024 * 1024


router = APIRouter(tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("/", response_class=HTMLResponse)
async def settings_index(request: Request, message: str = "", error: str = ""):
    """Display the WebZFS settings page with theme selector and session timeout."""
    active_theme = get_active_theme()
    theme_families = get_all_themes_for_template()
    theme_variables = get_theme_variables(active_theme)

    current_session_timeout = get_effective_session_timeout()

    active_corner_style = get_active_corner_style()
    corner_styles = get_all_corner_styles_for_template()

    response = templates.TemplateResponse(
        request,
        name="utils/settings/index.jinja",
        context={
            "active_theme": active_theme,
            "active_theme_name": THEME_REGISTRY.get(active_theme, active_theme),
            "theme_families": theme_families,
            "theme_variables": theme_variables,
            "current_session_timeout": current_session_timeout,
            "current_session_timeout_display": format_timeout_display(current_session_timeout),
            "default_session_timeout": DEFAULT_SESSION_TIMEOUT,
            "default_session_timeout_display": format_timeout_display(DEFAULT_SESSION_TIMEOUT),
            "session_timeout_presets": SESSION_TIMEOUT_PRESETS,
            "active_corner_style": active_corner_style,
            "active_corner_style_name": CORNER_STYLE_DISPLAY_NAMES.get(
                active_corner_style, active_corner_style
            ),
            "corner_styles": corner_styles,
            "message": message,
            "error": error,
            "page_title": "DataMax-zfs 设置",
        },
    )

    # When a theme or corner style was just changed, force HTMX to do a full
    # page refresh. HTMX hx-boost only swaps <body>, leaving stale stylesheet
    # references in <head> and the old body class. HX-Refresh on this 200
    # response (not the 303 redirect, which browsers follow transparently
    # before HTMX can see the header) tells HTMX to reload the entire page.
    if message and ("主题已切换" in message or "边角样式" in message):
        response.headers["HX-Refresh"] = "true"

    return response


@router.post("/apply-theme", response_class=HTMLResponse)
async def apply_theme(request: Request, theme: str = Form(...)):
    """Apply the selected theme and save to config."""
    if not is_valid_theme(theme):
        return RedirectResponse(
            url="/utils/settings?error=无效的主题选择",
            status_code=303,
        )

    success = save_theme(theme)
    if success:
        theme_name = THEME_REGISTRY.get(theme, theme)
        return RedirectResponse(
            url=f"/utils/settings?message=主题已切换为 {theme_name}",
            status_code=303,
        )
    else:
        return RedirectResponse(
            url="/utils/settings?error=保存主题失败。请检查项目配置目录 .config/webzfs/ 的文件权限",
            status_code=303,
        )


@router.post("/apply-corner-style", response_class=HTMLResponse)
async def apply_corner_style(request: Request, corner_style: str = Form(...)):
    """Apply the selected corner style and save to config."""
    if not is_valid_corner_style(corner_style):
        return RedirectResponse(
            url="/utils/settings?error=无效的边角样式选择",
            status_code=303,
        )

    success = save_corner_style(corner_style)
    if success:
        style_name = CORNER_STYLE_DISPLAY_NAMES.get(corner_style, corner_style)
        return RedirectResponse(
            url=f"/utils/settings?message=边角样式已切换为 {style_name}",
            status_code=303,
        )
    else:
        return RedirectResponse(
            url="/utils/settings?error=保存边角样式失败。请检查项目配置目录 .config/webzfs/ 的文件权限",
            status_code=303,
        )


@router.get("/theme-preview/{theme_id}", response_class=HTMLResponse)
async def theme_preview(request: Request, theme_id: str):
    """Return the theme preview partial with CSS variables for the selected theme."""
    if not is_valid_theme(theme_id):
        return HTMLResponse("<p class='text-danger-400'>无效的主题</p>")

    theme_variables = get_theme_variables(theme_id)
    theme_name = THEME_REGISTRY.get(theme_id, theme_id)

    return templates.TemplateResponse(
        request,
        name="utils/settings/preview_partial.jinja",
        context={
            "preview_theme_id": theme_id,
            "preview_theme_name": theme_name,
            "theme_variables": theme_variables,
        },
    )


@router.post("/save-session-timeout", response_class=HTMLResponse)
async def save_session_timeout_view(request: Request, session_timeout: int = Form(...)):
    """Save user-configured session timeout value."""
    if session_timeout not in VALID_TIMEOUT_VALUES:
        return RedirectResponse(
            url="/utils/settings?error=无效的会话超时选择",
            status_code=303,
        )

    try:
        save_session_timeout(session_timeout)
    except (ValueError, OSError) as exc:
        return RedirectResponse(
            url=f"/utils/settings?error=保存会话超时失败：{exc}",
            status_code=303,
        )

    display = format_timeout_display(session_timeout)
    return RedirectResponse(
        url=f"/utils/settings?message=会话超时已设置为 {display}。新会话将使用此值。",
        status_code=303,
    )


@router.post("/reset-session-timeout", response_class=HTMLResponse)
async def reset_session_timeout_view(request: Request):
    """Reset session timeout to the default value."""
    try:
        reset_session_timeout()
    except OSError as exc:
        return RedirectResponse(
            url=f"/utils/settings?error=重置会话超时失败：{exc}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/utils/settings?message=会话超时已重置为默认值（{format_timeout_display(DEFAULT_SESSION_TIMEOUT)}）",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Backup and Restore
# ---------------------------------------------------------------------------


def _redirect_with(message: str = "", error: str = "") -> RedirectResponse:
    """Build a redirect back to /utils/settings with a status message."""
    if error:
        return RedirectResponse(
            url=f"/utils/settings?error={quote(error)}", status_code=303
        )
    return RedirectResponse(
        url=f"/utils/settings?message={quote(message)}", status_code=303
    )


@router.post("/backup/export")
async def backup_export(
    request: Request,
    passphrase: str = Form(...),
    confirm_passphrase: str = Form(...),
    include_history: str = Form(None),
    include_secret: str = Form(None),
    include_system: str = Form(None),
):
    """
    Build an encrypted backup archive of WebZFS configuration and stream it
    to the user as a file download.
    """
    if passphrase != confirm_passphrase:
        return _redirect_with(error="两次输入的口令不一致。")
    if len(passphrase) < 8:
        return _redirect_with(error="口令长度至少为 8 个字符。")

    try:
        blob = backup_restore.create_archive(
            passphrase,
            include_history=bool(include_history),
            include_secret=bool(include_secret),
            include_system=bool(include_system),
        )
    except Exception as exc:
        logger.exception("Failed to build backup archive")
        return _redirect_with(error=f"构建备份存档失败：{exc}")

    filename = backup_restore.default_archive_filename()
    return StreamingResponse(
        io.BytesIO(blob),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(blob)),
        },
    )


@router.post("/backup/inspect", response_class=HTMLResponse)
async def backup_inspect(
    request: Request,
    archive: UploadFile = File(...),
    passphrase: str = Form(...),
):
    """
    Decrypt only the manifest of an uploaded archive and render a confirmation
    page listing what would be restored. The archive is stashed on disk under
    a session-bound token; the actual restore is performed by /backup/restore.
    """
    blob = await archive.read()
    if not blob:
        return _redirect_with(error="未上传任何文件。")
    if len(blob) > MAX_UPLOAD_SIZE:
        return _redirect_with(
            error=f"上传的文件过大（上限 {MAX_UPLOAD_SIZE // (1024 * 1024)} MB）。"
        )

    try:
        info = backup_restore.inspect_archive(blob, passphrase)
    except ValueError as exc:
        return _redirect_with(error=str(exc))
    except Exception as exc:
        logger.exception("Failed to inspect backup archive")
        return _redirect_with(error=f"检查存档失败：{exc}")

    try:
        token = backup_restore.stash_upload(blob)
    except Exception as exc:
        logger.exception("Failed to stash uploaded archive")
        return _redirect_with(error=f"暂存上传文件失败：{exc}")

    # Group manifest files by category for the confirmation UI.
    files_by_category: dict = {}
    for entry in info["manifest"].get("files", []):
        cat = entry.get("category", "unknown")
        files_by_category.setdefault(cat, []).append(entry)

    return templates.TemplateResponse(
        request,
        name="utils/settings/restore_confirm.jinja",
        context={
            "token": token,
            "header": info["header"],
            "manifest": info["manifest"],
            "summary": info["summary"],
            "files_by_category": files_by_category,
            "current_hostname": info["current_hostname"],
            "current_platform": info["current_platform"],
            "page_title": "确认恢复",
        },
    )


@router.post("/backup/restore")
async def backup_restore_apply(
    request: Request,
    token: str = Form(...),
    passphrase: str = Form(...),
    restore_config: str = Form(None),
    restore_ssh_key: str = Form(None),
    restore_sanoid: str = Form(None),
    restore_cron: str = Form(None),
    restore_env: str = Form(None),
):
    """
    Perform the actual restore using the stashed archive blob, the user's
    passphrase, and the per-category checkboxes.
    """
    selected = []
    if restore_config:
        selected.append(backup_restore.CATEGORY_CONFIG)
    if restore_ssh_key:
        selected.append(backup_restore.CATEGORY_SSH_KEY)
    if restore_sanoid:
        selected.append(backup_restore.CATEGORY_SANOID)
    if restore_cron:
        selected.append(backup_restore.CATEGORY_CRON)
    if restore_env:
        selected.append(backup_restore.CATEGORY_ENV)

    if not selected:
        return _redirect_with(error="未选择任何要恢复的类别。")

    try:
        blob = backup_restore.load_stash(token)
    except ValueError as exc:
        return _redirect_with(error=str(exc))

    try:
        result = backup_restore.restore_archive(
            blob, passphrase, selected_categories=selected
        )
    except ValueError as exc:
        return _redirect_with(error=str(exc))
    except Exception as exc:
        logger.exception("Failed to apply backup restore")
        return _redirect_with(error=f"恢复存档失败：{exc}")
    finally:
        backup_restore.discard_stash(token)

    restored_count = len(result.get("restored", []))
    failed_count = len(result.get("failed", []))
    if failed_count:
        return _redirect_with(
            error=(
                f"恢复完成但有错误：已恢复 {restored_count} 个文件，"
                f"{failed_count} 个失败。详情请查看服务器日志。"
            )
        )
    return _redirect_with(
        message=(
            f"恢复完成。已写入 {restored_count} 个文件。"
            f"现有文件已保留为 *.pre-restore-{result['timestamp']}。"
        )
    )
