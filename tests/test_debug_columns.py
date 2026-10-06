import unittest

from debug_columns import COLUMN_ENV_ORDER, OPTION_ENV_ORDER, _render_env
from setup_slack_list import OPTIONAL_COLUMN_ENVS


class DebugColumnsTests(unittest.TestCase):
    def test_render_includes_every_current_schema_mapping(self):
        values = {
            env_key: f"value-{index}"
            for index, env_key in enumerate((*COLUMN_ENV_ORDER, *OPTION_ENV_ORDER))
        }

        rendered = _render_env(values)

        for env_key, value in values.items():
            self.assertIn(f"{env_key}={value}", rendered)

    def test_render_marks_only_missing_optional_column(self):
        values = {
            env_key: f"value-{index}"
            for index, env_key in enumerate((*COLUMN_ENV_ORDER, *OPTION_ENV_ORDER))
            if env_key not in OPTIONAL_COLUMN_ENVS
        }

        rendered = _render_env(values)

        for env_key in OPTIONAL_COLUMN_ENVS:
            self.assertIn(f"# {env_key}=  # 선택 컬럼: 현재 List에 없음", rendered)


if __name__ == "__main__":
    unittest.main()
