import winreg


def apps_use_light_theme():
    # 🔴 Тема Windows (Settings -> Personalization -> Colors ->
    # Choose your mode): реестр Personalize\AppsUseLightTheme.
    # 1 = светлая, 0 = тёмная; нет ключа = считаем светлой.

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes"
            r"\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(
                key, "AppsUseLightTheme"
            )

            return bool(value)

    except OSError:
        return True


def system_colors():
    # 🔴 Цвета программы под тему системы (галочка настроек
    # «Использовать цвет системы»): яркости фона окна/списка
    # и цвет текста/иконок — те же ключи config, что двигают
    # бегунки «Яркость», но значения из темы Windows.

    if apps_use_light_theme():
        return {
            "window_color": 225,
            "list_color": 240,
            "icon_color": 35,
        }

    return {
        "window_color": 45,
        "list_color": 35,
        "icon_color": 220,
    }
