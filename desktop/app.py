"""CLPZ Desktop — main application entry point.

Starts the backend server, opens a native desktop window, and displays
the existing CLPZ web UI inside it.
"""
from __future__ import annotations

import sys
import webview

from desktop.server import BackendServer


def run(port: int = 8000) -> None:
    """Launch the CLPZ desktop application."""
    server = BackendServer(port=port)

    print(f"Starting CLPZ backend on port {port}...")
    server.start()
    print(f"Backend ready at {server.url()}")

    # Create the desktop window
    window = webview.create_window(
        title="CLPZ",
        url=server.url() + "/app?desktop=1",
        width=1200,
        height=800,
        min_size=(800, 600),
        text_select=True,
    )

    def on_closed():
        """Called when the window is closed — shut down the backend."""
        print("Window closed. Shutting down backend...")
        server.stop()

    window.events.closed += on_closed

    # Start the GUI event loop (blocks until window is closed)
    print("Opening desktop window...")
    webview.start(debug=("--debug" in sys.argv))

    # Cleanup in case events.closed didn't fire
    server.stop()


if __name__ == "__main__":
    run()
