# 🔴 Перевод интерфейса. Языков два: русский (по умолчанию) и
# английский. tr("Русская строка") возвращает английский перевод,
# если в config.json language="en"; иначе строку без изменений.
# Ключ словаря — РУССКАЯ строка как в коде; динамические строки —
# шаблоны с {} (вызов: tr("Удалить ({})").format(n)).
# Контекст: tr("Готово", "status") — отдельный перевод для
# одинаковых русских строк с разным смыслом.

_language = "ru"

EN = {

    # ---------- Общее ----------

    "Да": "Yes",
    "Нет": "No",
    "Отмена": "Cancel",
    "OK": "OK",
    "Закрыть": "Close",
    "Готово": "Done",
    "Готово\x00status": "Ready",
    "Все": "All",
    "Загрузить": "Load",
    "Удалить": "Delete",
    "Удалить все": "Delete all",
    "Дублировать": "Duplicate",
    "Переименовать": "Rename",
    "Добавить": "Add",
    "Изменить": "Edit",
    "Цвет": "Color",
    "По умолчанию": "Default",
    "Другой цвет...": "Other color...",

    # ---------- Главное окно / трей ----------

    "Показать": "Show",
    "Настройки": "Settings",
    "Выход": "Quit",
    "Программа свёрнута в трей": "The program is minimized to tray",
    "1 монитор": "1 monitor",
    "Несколько мониторов": "Multiple monitors",

    "Новый пресет": "New preset",
    "Разделитель": "Separator",
    "Загрузить пресет": "Load preset",
    "Обновить пресет": "Update preset",
    "Закрыть пресет": "Close preset",
    "Удалить пресет (Ctrl+клик — удалить ВСЕ пресеты)":
        "Delete preset (Ctrl+click — delete ALL presets)",
    "Управление вкладками-фильтрами": "Manage filter tabs",
    "Удалить вкладку (Ctrl+клик — удалить ВСЕ вкладки)":
        "Delete tab (Ctrl+click — delete ALL tabs)",

    # ---------- Вкладки ----------

    "Вкладка «Все» неизменяемая — сначала создайте свою "
    "(кнопка «Добавить»)":
        "The «All» tab is built-in — create your own first "
        "(the «Add» button)",

    "Новая вкладка": "New tab",
    "Название вкладки (фильтра):": "Tab (filter) name:",
    "Вкладка «{}» уже есть": "Tab «{}» already exists",
    "Вкладка «{}» создана": "Tab «{}» created",
    "{} (копия)": "{} (copy)",
    "{} (копия {})": "{} (copy {})",

    "Удалить вкладку": "Delete tab",
    "Удалить вкладку «{}»?\nСами пресеты останутся, но потеряют "
    "эту вкладку-тег.":
        "Delete tab «{}»?\nThe presets will remain, "
        "but they will lose this tab tag.",
    "Вкладок нет — удалять нечего": "No tabs — nothing to delete",
    "Удалить все вкладки": "Delete all tabs",
    "Зажат Ctrl: будут удалены ВСЕ вкладки ({} шт.), а не одна "
    "выбранная.\nСами пресеты останутся, но потеряют все "
    "вкладки-теги.":
        "Ctrl is held: ALL tabs ({}) will be deleted, not just "
        "the selected one.\nThe presets will remain, but they "
        "will lose all tab tags.",
    "Удалено вкладок: {}": "Tabs deleted: {}",
    "Переименовать вкладку": "Rename tab",
    "Новое название вкладки:": "New tab name:",
    "Дублировать вкладку": "Duplicate tab",
    "Цвет вкладки": "Tab color",

    # ---------- Цвета ----------

    "Красный": "Red",
    "Оранжевый": "Orange",
    "Жёлтый": "Yellow",
    "Зелёный": "Green",
    "Бирюзовый": "Teal",
    "Голубой": "Light blue",
    "Синий": "Blue",
    "Индиго": "Indigo",
    "Фиолетовый": "Purple",
    "Розовый": "Pink",
    "Лайм": "Lime",
    "Коричневый": "Brown",
    "Серый": "Grey",

    # ---------- Меню пресета ----------

    "Цвет применён к {} пресетам": "Color applied to {} presets",
    "Добавить разделитель": "Add separator",
    "Настроить": "Configure",
    "Закрыть окна пресета": "Close preset windows",
    "Обновить из текущих окон": "Update from current windows",
    "Тег (вкладка)...": "Tag (tab)...",
    "Удалить ({})": "Delete ({})",
    "Удалить пресет": "Delete preset",
    "Цвет пресета": "Preset color",
    "Создана копия «{}»": "Copy created: «{}»",
    "Добавлен разделитель «{}»": "Separator added: «{}»",
    "Теги применены к {} пресетам": "Tags applied to {} presets",
    "«{}»: удалено программ {}, папок {}":
        "«{}»: removed {} programs, {} folders",
    "Пресетов пока нет": "No presets yet",
    "Найден: «{}»": "Found: «{}»",

    # ---------- Загрузка пресетов ----------

    "Сначала выберите пресет": "Select a preset first",
    "Разделитель не загружается — это просто заголовок":
        "A separator is not loaded — it is just a header",
    "Дождитесь окончания загрузки":
        "Wait for the current load to finish",
    "текущие окна не закрыты": "current windows were not closed",
    "закрыто лишних {}": "closed {} extra",
    "Загружаю...": "Loading...",
    "Загружаю... {}/{}\n{}": "Loading... {}/{}\n{}",
    "Загружаю «{}» ({}/{})...": "Loading «{}» ({}/{})...",
    "Ошибка загрузки: {}": "Load error: {}",
    " …и ещё {}": " …and {} more",
    "Загружено пресетов: {} ({}{}); {}; поставлено {}, запущено {}, "
    "папок {}":
        "Presets loaded: {} ({}{}); {}; placed {}, launched {}, "
        "folders {}",
    "Применён «{}»: {}; поставлено {}, запущено {}, папок {}":
        "Applied «{}»: {}; placed {}, launched {}, folders {}",
    "Пресет «{}» обновлён": "Preset «{}» updated",
    "Закрыто {} окон пресета «{}»":
        "Closed {} windows of preset «{}»",
    "Загружено": "Loaded",

    # ---------- Удаление пресетов ----------

    "Удалить пресеты": "Delete presets",
    "Удалить {} выделенных пресетов?\n\n{}{}":
        "Delete {} selected presets?\n\n{}{}",
    "Удалить пресет «{}»?": "Delete preset «{}»?",
    "Удалено пресетов: {}": "Presets deleted: {}",
    "Пресетов нет — удалять нечего":
        "No presets — nothing to delete",
    "Зажат Ctrl: будут удалены ВСЕ пресеты ({} шт.), а не один "
    "выбранный.\nЭто действие необратимо.":
        "Ctrl is held: ALL presets ({}) will be deleted, not "
        "just the selected one.\nThis cannot be undone.",
    "Удалить ВСЕ пресеты ({} шт.)?\nЭто действие необратимо.":
        "Delete ALL presets ({})?\nThis cannot be undone.",
    "Удалить все пресеты": "Delete all presets",

    # ---------- Переименование ----------

    "Переименовать пресет": "Rename preset",
    "Имя «{}» уже занято": "Name «{}» is already taken",
    "Переименовано": "Renamed",

    # ---------- Превью ----------

    "Программы:": "Programs:",
    "Папки:": "Folders:",
    "Нет скриншота\n(пересохраните пресет)":
        "No screenshot\n(re-save the preset)",
    "Поиск пресета...": "Search presets...",
    "\nИзменён:\n{}": "\nUpdated:\n{}",
    "Программ: {}": "Programs: {}",
    "Папок: {}": "Folders: {}",
    "Мониторов: {}": "Monitors: {}",
    "подсказка: наведи курсор на превью или нажми выбранную клавишу":
        "hint: hover the cursor over the preview or press "
        "the selected key",

    # ---------- Редактор состава пресета ----------

    "Настроить пресет": "Configure preset",
    "«{}» — снимите галочки с лишнего":
        "«{}» — uncheck the items you don't need",
    "Удалить выбранные": "Delete selected",
    "В пресете нет программ и папок":
        "The preset has no programs or folders",
    "Программы ({})": "Programs ({})",
    "Папки ({})": "Folders ({})",
    "Программы (": "Programs (",
    "Папки (": "Folders (",

    # ---------- Окно тегов ----------

    "Убрать все теги": "Remove all tags",

    # ---------- Настройки ----------

    "Язык / Language": "Язык / Language",
    "Автозапуск": "Autostart",
    "Запускать при старте системы": "Run at system startup",
    "Главное окно": "Main window",
    "Использовать цвет системы": "Use system color",
    "Поверх всех окон": "Always on top",
    "Яркость главного окна": "Main window brightness",
    "Яркость списка пресетов": "Preset list brightness",
    "Прозрачность цвета пресетов": "Preset color opacity",
    "Кнопки вкладок — значки (иначе текст)":
        "Tab buttons as icons (otherwise text)",
    "Иконки": "Icons",
    "Яркость иконок": "Icon brightness",
    "Размер иконок": "Icon size",
    "Превью": "Preview",
    "Размер превью (пока не действует)":
        "Preview size (has no effect yet)",
    "Затемнение скриншота превью": "Preview screenshot dimming",
    "Размер текста инфо-плашки": "Info panel text size",
    "Прозрачность инфо-плашки": "Info panel opacity",
    "Поведение": "Behavior",
    "Показывать превью": "Show preview",
    "Сворачивать в трей": "Minimize to tray",
    "Запоминать положение окон": "Remember window positions",
    "Пасхалки": "Easter eggs",
    "Кавабанга !": "Kowabunga!",
    "Проверить обновления (v{})": "Check for updates (v{})",
    "Проверяю...": "Checking...",
    "Обновления: нет связи": "Updates: no connection",
    "У вас последняя версия ({})": "You have the latest version ({})",
    "Обновление": "Update",
    "Доступна версия {}. Скачать и установить?":
        "Version {} is available. Download and install?",
    "Обновить": "Update",
    "Позже": "Later",
    "Скачиваю... 0%": "Downloading... 0%",
    "Скачиваю... {}%": "Downloading... {}%",
    "Ошибка скачивания": "Download error",
    "Обновление скачано (исходники)":
        "Update downloaded (running from sources)",
    "Ошибка: {}": "Error: {}",
    "Обновление готово. Программа закроется, заменит exe "
    "и запустится сама.":
        "The update is ready. The program will close, replace "
        "the exe and restart itself.",
    "Установить": "Install",
    "Есть новая версия «{}»": "New version «{}» is available",

    # ---------- Исключения ----------

    "Исключения программ": "Program exclusions",
    "Программы и папки из этого списка полностью игнорируются: "
    "не сохраняются в пресет, не открываются при загрузке "
    "и никогда не закрываются.":
        "Programs and folders in this list are fully ignored: "
        "they are not saved into presets, not opened on load "
        "and never closed.",
    "<ввести вручную…>": "<type manually…>",
    "<выбрать файл или папку…>": "<pick a file or folder…>",
    "<ввести": "<type",
    "<выбрать": "<pick",
    "Исключение": "Exclusion",
    "Выберите окно, которое нужно игнорировать\n"
    "(или введите имя процесса / путь / часть заголовка):":
        "Pick a window to ignore\n"
        "(or type a process name / path / part of a window title):",
    "Имя процесса (zcode.exe), путь к файлу/папке\n"
    "или часть заголовка окна:":
        "Process name (zcode.exe), a file/folder path\n"
        "or part of a window title:",
    "Файл программы": "Program file",
    "Программы (*.exe *.vbs *.bat *.cmd *.ps1 *.lnk);;":
        "Programs (*.exe *.vbs *.bat *.cmd *.ps1 *.lnk);;",
    "Программы (*.exe *.vbs *.vbe *.bat *.cmd *.ps1 *.js *.hta "
    "*.lnk);;":
        "Programs (*.exe *.vbs *.vbe *.bat *.cmd *.ps1 *.js "
        "*.hta *.lnk);;",
    "Все файлы (*.*)": "All files (*.*)",
    "…или папка целиком": "…or an entire folder",

    # ---------- Пути запуска ----------

    "Пути запуска программ": "Program launch paths",
    "Если программа из пресета открывается неправильно — укажите "
    "для неё файл запуска или целую команду (exe, vbs, lnk или "
    "команда с аргументами, например для запуска через "
    "песочницу).":
        "If a program from a preset opens incorrectly — set its "
        "launch file or a full command (exe, vbs, lnk or a "
        "command with arguments, e.g. to run it through a "
        "sandbox).",
    "<выбрать файл программы…>": "<pick a program file…>",
    "Программа": "Program",
    "Выберите окно программы, для которой задаётся запуск\n"
    "(впишите имя процесса или выберите exe-файл):":
        "Pick the program window to set a launch for\n"
        "(type a process name or pick an exe file):",
    "Программа (её exe)": "Program (its exe)",
    "Имя процесса программы (как в диспетчере задач),\n"
    "например: powershell.exe":
        "Program process name (as in Task Manager),\n"
        "for example: powershell.exe",
    "Файл запуска (можно потом отредактировать команду)":
        "Launch file (the command can be edited later)",
    "Программы, скрипты, ярлыки (*.exe *.vbs *.vbe *.bat *.cmd "
    "*.ps1 *.js *.hta *.lnk);;":
        "Programs, scripts, shortcuts (*.exe *.vbs *.vbe *.bat "
        "*.cmd *.ps1 *.js *.hta *.lnk);;",
    "…или папка": "…or a folder",
    "Команда запуска": "Launch command",
    "Путь к файлу запуска или команда (можно с аргументами).\n"
    "Пример песочницы:\n"
    '"C:\\Program Files\\Sandboxie-Plus\\SandMan.exe" '
    '/box:DefaultBox "C:\\путь\\программа.exe"':
        "Path to the launch file or a command (arguments are "
        "allowed).\nSandbox example:\n"
        '"C:\\Program Files\\Sandboxie-Plus\\SandMan.exe" '
        '/box:DefaultBox "C:\\path\\program.exe"',
}


def set_language(lang):

    global _language

    _language = lang if lang in ("ru", "en") else "ru"


def language():

    return _language


def tr(text, ctx=""):

    if _language != "en":
        return text

    if ctx:
        return EN.get(
            f"{text}\x00{ctx}",
            EN.get(text, text),
        )

    return EN.get(text, text)
