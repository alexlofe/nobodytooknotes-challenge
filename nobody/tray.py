"""System tray icon for Nobody Took Notes."""

import threading
import webbrowser
from io import BytesIO

import pystray
from PIL import Image, ImageDraw


def create_icon(recording: bool = False) -> Image.Image:
    """Create a simple tray icon matching the brand colors."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if recording:
        draw.ellipse([8, 8, 56, 56], fill=(220, 38, 38))  # recording red
    else:
        draw.ellipse([8, 8, 56, 56], fill=(30, 58, 95))  # brand navy #1e3a5f
        draw.ellipse([20, 20, 44, 44], fill=(96, 165, 250))  # accent blue

    return img


class TrayApp:
    """System tray application."""

    def __init__(
        self,
        on_start: "(() -> None) | None" = None,
        on_stop: "(() -> None) | None" = None,
        on_quit: "(() -> None) | None" = None,
        port: int = 8765,
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_quit = on_quit
        self.port = port
        self.recording = False
        self.icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _toggle(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self.recording:
            if self.on_stop:
                self.on_stop()
            self.recording = False
        else:
            if self.on_start:
                self.on_start()
            self.recording = True
        icon.icon = create_icon(self.recording)
        icon.update_menu()

    def _open_ui(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}")

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self.recording and self.on_stop:
            self.on_stop()
        if self.on_quit:
            self.on_quit()
        icon.stop()

    def _create_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda _: "Stop Recording" if self.recording else "Start Recording",
                self._toggle,
            ),
            pystray.MenuItem("Open", self._open_ui, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def set_recording(self, recording: bool) -> None:
        """Update recording state (for external control)."""
        self.recording = recording
        if self.icon:
            self.icon.icon = create_icon(recording)
            self.icon.update_menu()

    def run(self) -> None:
        """Run the tray icon (blocks)."""
        self.icon = pystray.Icon(
            "nobody-took-notes",
            create_icon(False),
            "Nobody Took Notes",
            menu=self._create_menu(),
        )
        self.icon.run()

    def run_detached(self) -> None:
        """Run the tray icon in a background thread."""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self.icon:
            self.icon.stop()
