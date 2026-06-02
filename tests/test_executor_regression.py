"""CommandExecutor 的回归测试。

覆盖本次修复涉及的两条链路：

- `view_mode=raw` 时跳过增强层与 observation 组装；
- 控制台输出在 GBK 编码下遇到不可编码字符时不崩溃。
"""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from efinance_cli.command_catalog import get_shared_command_definition
from efinance_cli.executor import CommandExecutor
from efinance_cli.models import (
    BackendName,
    BackendSelection,
    CommandSpec,
    InvocationRequest,
    InvocationResult,
    OutputOptions,
    WatchOptions,
)


class _FakeStdout(io.StringIO):
    """模拟带 GBK 编码的控制台 stdout。"""

    encoding = "gbk"


class ExecutorRegressionTest(unittest.TestCase):
    """验证 executor 的 raw 视图与编码兜底修复。"""

    def _build_request(self, view_mode: str = "observation") -> InvocationRequest:
        definition = get_shared_command_definition("stock.price.history")
        return InvocationRequest(
            spec=CommandSpec(
                module_name="shared",
                function_name="stock.price.history",
                callback=lambda **_: None,
                help_text="test",
                cli_path=("stock", "price", "history"),
                allow_watch=True,
            ),
            kwargs={"stock_codes": ["000001"]},
            output=OutputOptions(format_name="json", view_mode=view_mode),
            watch=WatchOptions(enabled=False),
            command_definition=definition,
            backend_selection=BackendSelection(
                requested=BackendName.EFINANCE,
                resolved=BackendName.EFINANCE,
                source="explicit",
            ),
        )

    def test_raw_view_skips_enrichment_and_observation(self) -> None:
        executor = CommandExecutor()
        request = self._build_request(view_mode="raw")
        raw_payload = {
            "contract_name": "history-bars",
            "data": [{"symbol": "000001", "close": 10.5}],
            "raw_payload": {"foo": "bar"},
            "provider_fields": {},
            "metadata": {},
        }

        with patch.object(executor, "_execute_shared_command", return_value=raw_payload):
            with patch("efinance_cli.executor.enrich_market_data") as mock_enrich:
                with patch("efinance_cli.executor.build_observation_output") as mock_observation:
                    result = executor.invoke(request)

        self.assertIsInstance(result, InvocationResult)
        self.assertEqual(result.value, raw_payload)
        mock_enrich.assert_not_called()
        mock_observation.assert_not_called()

    def test_observation_view_keeps_existing_pipeline(self) -> None:
        executor = CommandExecutor()
        request = self._build_request(view_mode="observation")

        with patch.object(executor, "_execute_shared_command", return_value={"rows": []}):
            with patch("efinance_cli.executor.enrich_market_data", return_value={"enriched": True}) as mock_enrich:
                with patch(
                    "efinance_cli.executor.build_observation_output",
                    return_value={"observed": True},
                ) as mock_observation:
                    result = executor.invoke(request)

        self.assertEqual(result.value, {"observed": True})
        mock_enrich.assert_called_once()
        mock_observation.assert_called_once()

    def test_emit_replaces_console_unencodable_characters(self) -> None:
        executor = CommandExecutor()
        request = self._build_request()
        result = InvocationResult(value="bad:\ufffd")

        with patch.object(executor, "_render", return_value="bad:\ufffd"):
            with patch("efinance_cli.executor.sys.stdout", new=_FakeStdout()):
                with patch("click.echo") as mock_echo:
                    executor._emit(request, result)

        emitted = mock_echo.call_args.args[0]
        self.assertEqual(emitted, "bad:?")

    def test_emit_file_output_keeps_user_encoding(self) -> None:
        executor = CommandExecutor()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "result.txt"
            request = self._build_request()
            request.output.output_path = str(output_path)
            request.output.encoding = "utf-8"
            result = InvocationResult(value="bad:\ufffd")

            with patch.object(executor, "_render", return_value="bad:\ufffd"):
                with patch("click.echo"):
                    executor._emit(request, result)

            self.assertEqual(output_path.read_text(encoding="utf-8"), "bad:\ufffd")


if __name__ == "__main__":
    unittest.main()
