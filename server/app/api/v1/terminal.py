"""WebSocket terminal endpoint for running shell commands."""

import asyncio
import os
import pty
import select
import struct
import subprocess
import termios
import fcntl
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_ws
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


class TerminalSession:
    """Manages a PTY session for WebSocket terminal."""

    def __init__(self):
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False

    def start(self, rows: int = 24, cols: int = 80):
        """Start a new PTY shell session."""
        # Fork a new process with a pseudo-terminal
        self.pid, self.fd = pty.fork()

        if self.pid == 0:
            # Child process - exec shell
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["COLORTERM"] = "truecolor"
            env["LANG"] = "en_US.UTF-8"

            # Change to home directory
            home = os.path.expanduser("~")
            try:
                os.chdir(home)
            except OSError:
                # Fallback to /tmp if home doesn't exist
                os.chdir("/tmp")

            # Find available shell
            shell = "/bin/bash"
            if not os.path.exists(shell):
                shell = "/bin/sh"

            # Execute shell
            os.execvpe(shell, [shell, "-l"], env)
        else:
            # Parent process - set non-blocking
            self.running = True

            # Set terminal size
            self.resize(rows, cols)

            # Set non-blocking
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def resize(self, rows: int, cols: int):
        """Resize the PTY."""
        if self.fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def write(self, data: bytes):
        """Write data to the PTY."""
        if self.fd is not None and self.running:
            os.write(self.fd, data)

    def read(self) -> Optional[bytes]:
        """Read available data from the PTY."""
        if self.fd is None or not self.running:
            return None

        try:
            readable, _, _ = select.select([self.fd], [], [], 0.01)
            if readable:
                return os.read(self.fd, 4096)
        except (OSError, IOError):
            self.running = False
        return None

    def stop(self):
        """Stop the PTY session."""
        self.running = False
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

        if self.pid is not None:
            try:
                os.kill(self.pid, 9)
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.pid = None


# Store active terminal sessions
active_sessions: dict[str, TerminalSession] = {}


@router.websocket("")
async def terminal_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint for terminal sessions.

    Protocol:
    - Client sends: {"type": "input", "data": "..."} for input
    - Client sends: {"type": "resize", "rows": N, "cols": N} for resize
    - Server sends: {"type": "output", "data": "..."} for output
    - Server sends: {"type": "error", "message": "..."} for errors
    """
    await websocket.accept()

    # Validate token
    from app.core.security import decode_access_token
    from app.core.database import async_session_factory
    from sqlalchemy import select

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close()
            return
    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Authentication failed: {str(e)}"})
        await websocket.close()
        return

    # Create terminal session
    session = TerminalSession()
    session_id = f"{user_id}-{id(websocket)}"
    active_sessions[session_id] = session

    try:
        # Start PTY
        session.start(rows=24, cols=80)

        # Send initial message
        await websocket.send_json({
            "type": "output",
            "data": "\r\n\x1b[1;32mTrustModel Terminal\x1b[0m - Connected\r\n\r\n"
        })

        # Read/write loop
        while session.running:
            # Check for output from PTY
            output = session.read()
            if output:
                await websocket.send_json({
                    "type": "output",
                    "data": output.decode("utf-8", errors="replace")
                })

            # Check for input from WebSocket (with timeout)
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=0.05
                )

                if message.get("type") == "input":
                    data = message.get("data", "")
                    session.write(data.encode("utf-8"))

                elif message.get("type") == "resize":
                    rows = message.get("rows", 24)
                    cols = message.get("cols", 80)
                    session.resize(rows, cols)

                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        session.stop()
        active_sessions.pop(session_id, None)


@router.get("/active")
async def get_active_terminals(
    current_user: User = Depends(get_current_user_ws),
):
    """Get count of active terminal sessions."""
    return {"active_sessions": len(active_sessions)}
