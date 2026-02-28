from PyQt6.QtGui import QGuiApplication


def get_theme_colors(theme, fallback_palette=None):
    requested_theme = str(theme or "system").lower()
    if requested_theme not in {"system", "dark", "light"}:
        requested_theme = "system"

    if requested_theme == "light":
        is_light_mode = True
    elif requested_theme == "dark":
        is_light_mode = False
    else:
        palette = fallback_palette
        if palette is None:
            app = QGuiApplication.instance()
            if app is not None:
                palette = app.palette()
        is_light_mode = palette.color(palette.ColorRole.Window).lightness() > 128 if palette is not None else False

    accent_color = "#5aa9ff"

    if is_light_mode:
        colors = {
            "bg_color": "#f5f5f5",
            "text_color": "#000000",
            "border_color": "#c7ced8",
            "input_bg": "#ffffff",
            "btn_bg": "#e7ebf0",
            "btn_hover": "#dde4ec",
            "btn_text": "#000000",
            "muted_text": "#5e6a78",
            "placeholder": "#7e8793",
            "accent_color": accent_color,
        }
        resolved_theme = "light"
    else:
        colors = {
            "bg_color": "#25282e",
            "text_color": "#e5e9ef",
            "border_color": "#4a5260",
            "input_bg": "#31363f",
            "btn_bg": "#3b424d",
            "btn_hover": "#495261",
            "btn_text": "#ffffff",
            "muted_text": "#97a3b3",
            "placeholder": "#7f8b9a",
            "accent_color": accent_color,
        }
        resolved_theme = "dark"

    colors["resolved_theme"] = resolved_theme
    colors["requested_theme"] = requested_theme
    return colors
