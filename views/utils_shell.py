from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse

from auth.dependencies import get_current_user
from config.templates import templates
from services.shell import get_shell_session, clear_shell_session

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/")
def index(request: Request, username: str = Depends(get_current_user)):
    """Display the shell interface."""
    session = get_shell_session(username)
    context = {
        "cwd": session.cwd,
    }
    return templates.TemplateResponse(request, name="utils/shell/index.jinja", context=context)


@router.post("/command")
def command(
    request: Request,
    input_command: Annotated[str, Form()],
    username: str = Depends(get_current_user),
):
    """Execute a shell command and return the result."""
    session = get_shell_session(username)
    
    context: dict[str, Any] = {
        "input_command": input_command,
        "cwd": session.cwd,
    }

    try:
        output, error = session.execute_command(input_command)
        context["output"] = output
        if error:
            context["error"] = error
        # Update CWD after command execution (in case of cd)
        context["cwd"] = session.cwd
    except Exception as exc:
        context["error"] = str(exc)

    return templates.TemplateResponse(
        request, name="utils/shell/command_result.jinja", context=context
    )


@router.get("/cwd")
def get_cwd(request: Request, username: str = Depends(get_current_user)):
    """Get the current working directory for HTMX updates."""
    session = get_shell_session(username)
    return templates.TemplateResponse(
        request,
        name="utils/shell/cwd.jinja",
        context={"cwd": session.cwd},
    )


@router.get("/download-history")
def download_history(username: str = Depends(get_current_user)):
    """Download the shell command history as a text file."""
    session = get_shell_session(username)
    history_text = session.get_history_text()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"shell_history_{timestamp}.txt"
    
    return PlainTextResponse(
        content=history_text,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/clear")
def clear(username: str = Depends(get_current_user)):
    """Clear the shell session (reset history and cwd)."""
    clear_shell_session(username)
    return {"status": "success", "message": "Shell 会话已清除"}


@router.post("/autocomplete")
def autocomplete(
    request: Request,
    partial: Annotated[str, Form()],
    username: str = Depends(get_current_user),
):
    """Get tab completion suggestions for a partial command."""
    session = get_shell_session(username)
    suggestions = session.tab_complete(partial)
    return {"suggestions": suggestions}
