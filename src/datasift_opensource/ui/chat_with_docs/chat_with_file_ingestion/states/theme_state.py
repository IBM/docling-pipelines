import reflex as rx


class ThemeState(rx.State):
    """State for managing light/dark mode theme."""

    is_dark_mode: bool = False

    @rx.event
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
