import json

from core.preset import Preset


class PresetRepository:

    @staticmethod
    def load(file_name):

        try:

            with open(

                file_name,

                "r",

                encoding="utf-8"

            ) as file:

                data = json.load(file)

        except Exception:

            return []

        presets = []

        for item in data:

            try:

                presets.append(

                    Preset.from_dict(item)

                )

            except Exception:

                pass

        # 🔴 БЕЗ СОРТИРОВКИ: порядок в presets.json задаёт владелец
        # перетаскиванием строк в списке (v0.4.4). Раньше список
        # принудительно сортировался по алфавиту и порядок терялся.

        return presets

    # --------------------------------------------------

    @staticmethod
    def save(

        file_name,

        presets,

    ):

        with open(

            file_name,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                [

                    preset.to_dict()

                    for preset in presets

                ],

                file,

                indent=4,

                ensure_ascii=False

            )