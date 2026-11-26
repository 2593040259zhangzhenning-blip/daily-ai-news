import io
import json
import os
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from scripts import generate_issue as signal

ROOT = signal.ROOT
NOW = datetime(2026, 11, 26, 21, 18, tzinfo=signal.BEIJING)
DAY = NOW.date()
MORNING = "2026-11-26-1morning"
EVENING = "2026-11-26-2evening"
SOURCE_URL = "https://example.com/news/release"
SOURCE = {"name": "测试信源", "url": SOURCE_URL}
USAGE = {"total_input_tokens": 300, "total_thought_tokens": 80, "total_output_tokens": 200}


def issue(edition="morning"):
    return {
        "key": signal.issue_key(DAY, edition),
        "date": DAY.isoformat(),
        "edition": edition,
        "createdAt": NOW.isoformat(),
        "headline": "本期新闻",
        "items": [{
            "cat": "model", "title": "模型更新", "body": "厂商宣布新模型。描述更新细节。",
            "score": 8, "tier": "lead" if edition == "morning" else "must",
            "summary": "一句摘要", "sources": [SOURCE.copy()],
        }],
        "scan": {"checked": ["测试信源"], "candidates": 2},
    }


def special():
    return {
        "slug": "test-event", "date": DAY.isoformat(), "title": "测试发布会",
        "org": "测试公司", "cat": "product", "summary": "发布会专题摘要。",
        "highlights": [{"title": str(n), "body": "更新", "score": n} for n in (7, 8, 9)],
        "sources": [SOURCE.copy()],
    }


def model():
    return {
        "slug": "test-model", "date": DAY.isoformat(),
        "name": "Test Model", "org": "测试公司", "self": "Test Model",
        "board": {
            "source": "Artificial Analysis 综合指数 v4.3",
            "asof": DAY.isoformat(),
            "rows": [
                {"name": "Top Model", "score": 60},
                {"name": "Test Model", "score": 57},
                {"name": "Model C", "score": 55},
                {"name": "Model D", "score": 53},
                {"name": "Model E", "score": 51},
                {"name": "Model F", "score": 49},
            ],
        },
        "use": [{"where": "Test App", "value": "Pro 起", "note": "$20 / 月"}],
        "sources": [SOURCE.copy()],
    }


def response(text, *, searched=True, url=SOURCE_URL):
    annotation = SimpleNamespace(type="url_citation", title="测试来源标题", url=url)
    block = SimpleNamespace(type="text", text=text, annotations=[annotation])
    steps = [SimpleNamespace(type="google_search_result")] if searched else []
    steps.append(SimpleNamespace(type="model_output", content=[block]))
    return SimpleNamespace(status="completed", output_text=text, steps=steps, usage=SimpleNamespace(**USAGE))


class SchemaTests(unittest.TestCase):
    def test_full_response_schema_serializes(self):
        response_format = json.loads(json.dumps(signal.RESPONSE_FORMAT))
        self.assertEqual(response_format["mime_type"], "application/json")
        root = response_format["schema"]
        self.assertEqual(root["required"], ["status"])
        issue_schema = root["properties"]["issue"]
        fields = issue_schema["properties"]
        self.assertTrue({"key", "date", "edition", "headline", "items", "scan", "watch", "updates"} <= fields.keys())
        self.assertTrue({"key", "date", "edition", "headline", "items", "scan"} <= set(issue_schema["required"]))
        self.assertEqual(fields["scan"]["required"], ["checked", "candidates"])
        item = fields["items"]["items"]
        self.assertIn("summary", item["properties"])
        self.assertTrue({"cat", "title", "body", "score", "tier", "sources"} <= set(item["required"]))
        special_schema = root["properties"]["special"]
        self.assertTrue({"title", "highlights", "sources"} <= set(special_schema["required"]))
        model_schema = root["properties"]["model"]
        self.assertTrue({"self", "board", "use", "sources"} <= set(model_schema["required"]))
        model_fields = model_schema["properties"]
        self.assertEqual(model_fields["board"]["required"], ["source", "asof", "rows"])
        self.assertEqual(model_fields["board"]["properties"]["rows"]["items"]["required"], ["name", "score"])
        self.assertEqual(model_fields["use"]["items"]["required"], ["where", "value"])
        for record in (item, special_schema, model_schema, fields["updates"]["items"]):
            with self.subTest(required=record["required"]):
                source_array = record["properties"]["sources"]
                self.assertEqual(source_array["minItems"], 1)
                source = source_array["items"]
                self.assertEqual(source["required"], ["name", "url"])
                self.assertEqual(source["properties"]["name"]["type"], "string")
                self.assertEqual(source["properties"]["url"]["type"], "string")
                self.assertFalse(source["additionalProperties"])


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(TemporaryDirectory(dir=ROOT, prefix=".signal-test-")))
        (self.folder / "scripts").mkdir()
        (self.folder / "data" / "issues").mkdir(parents=True)
        (self.folder / "temp").mkdir()
        shutil.copy2(ROOT / "scripts" / "add_issue.py", self.folder / "scripts")
        for name in signal.DOCS:
            shutil.copy2(ROOT / name, self.folder)
        self.enterContext(patch.multiple(signal, ROOT=self.folder, TMP=self.folder / "temp"))
        self.enterContext(patch.dict(os.environ, {name: "" for name in (*signal.SECRET_NAMES, "GITHUB_OUTPUT")}))
        self.factory = self.enterContext(patch.object(signal, "gemini_client"))
        self.create = self.factory.return_value.__enter__.return_value.interactions.create
        self.stdout = self.enterContext(redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(redirect_stderr(io.StringIO()))

    def generate(self, *argv, now=NOW):
        return signal.generate(signal.arguments(argv), now)

    def save_morning(self):
        signal.write_json(self.folder / "data" / "issues" / f"{MORNING}.json", issue())

    def test_existing_requested_issue_skips_without_sdk(self):
        self.save_morning()
        self.generate("--edition", "morning")
        self.factory.assert_not_called()
        self.assertIn(f"{MORNING} 已存在", self.stdout.getvalue())

    def test_evening_before_six_backfills_previous_morning(self):
        mock_payload = json.dumps({"status": "publish", "issue": issue()}, ensure_ascii=False)
        self.create.return_value = response(mock_payload)
        self.generate("--edition", "evening", "--dry-run", now=NOW.replace(day=27, hour=2))
        saved = json.loads((signal.TMP / "signal-dry-run-preview.json").read_text())
        self.assertEqual(saved["issue"]["key"], MORNING)
        self.assertEqual(saved["issue"]["edition"], "morning")
        self.assertEqual(list((self.folder / "data" / "issues").iterdir()), [])
        self.assertIn("晚间任务补做早间", self.create.call_args.kwargs["input"])
        self.assertIn("已补上", self.stdout.getvalue())

    def test_explicit_date_overrides_midnight_rollover(self):
        args = signal.arguments(["--edition", "evening", "--date", "2026-11-27"])
        self.assertEqual(signal.edition_date(args, NOW.replace(day=27, hour=1)), date(2026, 11, 27))

    def test_evening_skip_preserves_data_and_checks_seven_am(self):
        self.save_morning()
        self.create.return_value = response('{"status":"skip"}')
        self.generate("--edition", "evening")
        self.assertEqual(self.create.call_count, 1)
        self.assertIn("2026-11-26T07:00+08:00", self.create.call_args.kwargs["input"])
        self.assertIn(MORNING, self.create.call_args.kwargs["input"])
        self.assertIn("无重要增补", self.stdout.getvalue())
        self.assertFalse((self.folder / "data" / "index.json").exists())

    def test_evening_skip_without_search_is_retried(self):
        self.save_morning()
        self.create.side_effect = [response('{"status":"skip"}', searched=False), response('{"status":"skip"}')]
        self.generate("--edition", "evening")
        self.assertEqual(self.create.call_count, 2)
        self.assertIn("没有 Google Search 结果", self.create.call_args.kwargs["input"])

    def test_evening_can_publish_only_a_card(self):
        self.save_morning()
        self.create.return_value = response(json.dumps({"status": "publish", "model": model()}))
        self.generate("--edition", "evening")
        self.assertFalse((self.folder / "data" / "issues" / f"{EVENING}.json").exists())
        latest = json.loads((self.folder / "data" / "latest.json").read_text())
        self.assertEqual(latest["lead"]["model"], "test-model")

    def test_model_card_uses_board_ties_and_preserves_optional_fields(self):
        card = model()
        card["date"] = "2026-11-24"
        card["color"] = "#D97757"
        card["sibling"] = "Model C"
        card["board"]["rows"][2]["score"] = 57
        card["board"]["prev"] = {"name": "Previous Model", "score": 47}
        self.create.return_value = response(json.dumps({"status": "publish", "issue": issue(), "model": card}))
        self.generate("--edition", "morning", "--dry-run")
        saved = json.loads((signal.TMP / "signal-dry-run-preview.json").read_text())["model"]
        self.assertEqual(saved["rankText"], "并列第 2")
        self.assertEqual([row["rank"] for row in saved["board"]["rows"]][:4], [1, 2, 2, 4])
        self.assertEqual(saved["date"], "2026-11-24")
        for field in ("color", "sibling", "use", "sources"):
            self.assertEqual(saved[field], card[field])
        self.assertEqual(saved["board"]["prev"], card["board"]["prev"])

    def test_model_outside_top_five_is_rejected(self):
        card = model()
        card["board"]["rows"][1]["score"] = 40
        self.create.return_value = response(json.dumps({"status": "publish", "issue": issue(), "model": card}))
        with self.assertRaisesRegex(signal.SignalError, "两次自动修复"):
            self.generate("--edition", "morning", "--dry-run")
        self.assertIn("没进前 5", self.stderr.getvalue())
        self.assertIn("model 字段键名=", self.stderr.getvalue())

    def test_invalid_json_then_validator_stderr_then_success(self):
        bad = issue()
        bad["items"][0]["tier"] = "must"
        good = {"status": "publish", "issue": issue(), "special": special(), "model": model()}
        self.create.side_effect = [
            response("truncated {"),
            response(json.dumps({"status": "publish", "issue": bad})),
            response("\x60\x60\x60json\n" + json.dumps(good) + "\n\x60\x60\x60"),
        ]
        self.generate("--edition", "morning")
        self.assertEqual(self.create.call_count, 3)
        second, third = [call.kwargs["input"] for call in self.create.call_args_list[1:]]
        self.assertIn("JSON 无效", second)
        self.assertIn("错误：早间一期的头条（lead）必须恰好 1 条，现在是 0 条", third)
        data = self.folder / "data"
        self.assertTrue((data / "issues" / f"{MORNING}.json").is_file())
        self.assertTrue((data / "specials" / "test-event.json").is_file())
        self.assertTrue((data / "models" / "test-model.json").is_file())
        daily = json.loads((data / "days" / f"{DAY}.json").read_text())
        self.assertEqual(len(daily["issues"]), 1)
        self.assertEqual(daily["specials"][0]["slug"], "test-event")
        self.assertEqual(daily["models"][0]["rankText"], "第 2")
        latest = json.loads((data / "latest.json").read_text())
        self.assertEqual(latest["lead"]["model"], "test-model")

    def test_failed_card_does_not_persist_valid_issue(self):
        bad = special()
        bad["highlights"] = []
        self.create.return_value = response(json.dumps({"status": "publish", "issue": issue(), "special": bad}))
        with self.assertRaisesRegex(signal.SignalError, "两次自动修复"):
            self.generate("--edition", "morning")
        self.assertEqual(self.create.call_count, 3)
        self.assertFalse((self.folder / "data" / "issues" / f"{MORNING}.json").exists())
        self.assertFalse((self.folder / "data" / "index.json").exists())

    def test_force_replaces_existing_issue(self):
        self.save_morning()
        revised = issue()
        revised["headline"] = "修订版头条"
        self.create.return_value = response(json.dumps({"status": "publish", "issue": revised}))
        self.generate("--edition", "morning", "--force")
        saved = json.loads((self.folder / "data" / "issues" / f"{MORNING}.json").read_text())
        self.assertEqual(saved["headline"], "修订版头条")

    def test_actions_notifies_only_after_publication_step(self):
        output = self.folder / "github-output"
        morning = issue()
        morning["headline"] = "本期\n新闻"
        self.create.return_value = response(json.dumps({"status": "publish", "issue": morning}))
        with patch.dict(os.environ, GITHUB_OUTPUT=str(output)), patch.object(signal, "send_notification") as notify:
            self.generate("--edition", "morning", "--dry-run")
            self.assertFalse(output.exists())
            self.generate("--edition", "morning")
        notify.assert_not_called()
        lines = output.read_text().splitlines()
        self.assertEqual(lines[0], "subject=早间：本期 新闻")
        self.assertEqual(json.loads(lines[1].removeprefix("notification=")).splitlines(),
                         ["今日头条：模型更新", "打开 Signal 看全文"])

    def test_non_http_link_rejected_and_annotation_can_repair_missing_url(self):
        bad = issue()
        bad["items"][0]["sources"][0]["url"] = "javascript:void(0)"
        good = issue()
        good["items"][0]["sources"] = [{"name": "测试信源", "citationTitle": "测试来源标题"}]
        self.create.side_effect = [
            response(json.dumps({"status": "publish", "issue": bad})),
            response(json.dumps({"status": "publish", "issue": good})),
        ]
        self.generate("--edition", "morning", "--dry-run")
        self.assertIn("需要有效的 HTTP(S) 来源链接", self.create.call_args.kwargs["input"])
        self.assertIn('items[0].sources[0] 字段键名=["name", "url"]', self.stderr.getvalue())
        saved = json.loads((signal.TMP / "signal-dry-run-preview.json").read_text())
        self.assertEqual(saved["issue"]["items"][0]["sources"], [SOURCE])

    def test_source_aliases_and_fallback_names(self):
        citations = {signal.url_key(SOURCE_URL): (SOURCE_URL, "引用标题")}
        cases = (
            ({"source": {"title": " 标题 ", "url": SOURCE_URL}}, citations, "标题"),
            ({"sources": [{"site": "站点", "url": SOURCE_URL}]}, citations, "站点"),
            ({"sources": [{"publisher": "发布方", "url": SOURCE_URL}]}, citations, "发布方"),
            ({"sources": [{"source": "来源名", "url": SOURCE_URL}]}, citations, "来源名"),
            ({"sources": [{"url": SOURCE_URL}]}, citations, "引用标题"),
            ({"sources": [{"url": SOURCE_URL}]}, {}, "example.com"),
            ({"source": SOURCE_URL}, citations, "example.com"),
        )
        for record, evidence, name in cases:
            with self.subTest(record=record):
                signal.verify_sources(record, "items[0]", evidence)
                self.assertEqual(record, {"sources": [{"name": name, "url": SOURCE_URL}]})

    def test_trailing_slash_matches_but_unannotated_link_can_publish(self):
        morning = issue()
        extra = "https://other.example.com/announcement"
        morning["items"][0]["sources"] = [{"url": SOURCE_URL + "/"}, {"url": extra}]
        self.create.return_value = response(json.dumps({"status": "publish", "issue": morning}))
        self.generate("--edition", "morning", "--dry-run")
        self.assertEqual(self.create.call_count, 1)
        saved = json.loads((signal.TMP / "signal-dry-run-preview.json").read_text())
        self.assertEqual(saved["issue"]["items"][0]["sources"], [
            {"name": "测试来源标题", "url": SOURCE_URL},
            {"name": "other.example.com", "url": extra},
        ])
        self.assertIn("WARNING items[0].sources[1]", self.stderr.getvalue())
        self.assertNotIn("WARNING items[0].sources[0]", self.stderr.getvalue())

    def test_missing_scan_uses_normalized_source_names(self):
        morning = issue()
        morning.pop("scan")
        item = morning["items"][0]
        item.pop("sources")
        item["source"] = {"publisher": "实查信源", "url": SOURCE_URL}
        self.create.return_value = response(json.dumps({"status": "publish", "issue": morning}))
        self.generate("--edition", "morning", "--dry-run")
        saved = json.loads((signal.TMP / "signal-dry-run-preview.json").read_text())["issue"]
        self.assertEqual(saved["scan"], {"checked": ["实查信源"], "candidates": 1})

    def test_source_diagnostic_redacts_and_truncates_preview(self):
        marker = "test-only-sensitive-marker"
        source = {"token": marker, "url": "javascript:" + "x" * 400}
        with self.assertRaises(signal.ValidationError) as failure:
            signal.verify_sources({"sources": [source]}, "items[0]", {})
        with patch.dict(os.environ, GEMINI_API_KEY=marker):
            signal.validation_detail(failure.exception)
        diagnostic = self.stderr.getvalue().strip()
        self.assertIn('items[0].sources[0] 字段键名=["token", "url"]', diagnostic)
        preview = diagnostic.split("预览=", 1)[1]
        self.assertIn("[REDACTED]", preview)
        self.assertNotIn(marker, preview)
        self.assertEqual(len(preview), 300)
        self.assertTrue(preview.endswith("…"))

    def test_default_and_overrides_forward_thinking_search_and_log_usage(self):
        self.create.return_value = response(json.dumps({"status": "publish", "issue": issue()}))
        with patch.dict(os.environ, GEMINI_MODEL=signal.DEFAULT_MODEL, GEMINI_THINKING_LEVEL="high"):
            self.generate("--edition", "morning", "--dry-run")
            self.assertEqual(self.create.call_args.kwargs["generation_config"], {"thinking_level": "high"})
        with patch.dict(os.environ, GEMINI_MODEL="test-model", GEMINI_THINKING_LEVEL="low"):
            self.generate("--edition", "morning", "--dry-run", "--thinking-level", "xhigh")
            request = self.create.call_args.kwargs
            self.assertEqual(request["model"], "test-model")
            self.assertEqual(request["generation_config"], {"thinking_level": "xhigh"})
            self.assertEqual(request["tools"], [{"type": "google_search"}])
            self.assertIn("total_thought_tokens=80", self.stdout.getvalue())

    def test_secret_from_api_exception_is_not_logged(self):
        marker = "test-only-sensitive-marker"
        self.create.side_effect = RuntimeError(marker)
        with patch.dict(os.environ, GEMINI_API_KEY=marker):
            with self.assertRaisesRegex(signal.SignalError, "RuntimeError") as result:
                self.generate("--edition", "morning", "--dry-run")
        self.assertNotIn(marker, str(result.exception) + self.stdout.getvalue() + self.stderr.getvalue())


@unittest.skipUnless(find_spec("httpx2"), "本地未安装 google-genai 3.6.1")
class SdkTests(unittest.TestCase):
    def test_installed_sdk_serializes_neon_request_and_parses_citations(self):
        import httpx2
        from google import genai

        requests = []
        text = '{"status":"skip"}'

        def handle(request):
            requests.append(request)
            return httpx2.Response(200, json={
                "id": "test-interaction", "object": "interaction", "status": "completed",
                "model": signal.DEFAULT_MODEL, "created": "2026-11-26T13:18:00Z",
                "updated": "2026-11-26T13:18:00Z", "usage": {"total_tokens": 580, **USAGE},
                "steps": [
                    {"type": "google_search_result", "call_id": "test-call", "result": []},
                    {"type": "model_output", "content": [{
                        "type": "text", "text": text, "annotations": [{
                            "type": "url_citation", "url": SOURCE_URL, "title": "测试信源",
                            "start_index": 0, "end_index": len(text),
                        }],
                    }]},
                ],
            })

        args = signal.arguments(["--edition", "evening", "--model", signal.DEFAULT_MODEL, "--thinking-level", "high"])
        options = {"client_args": {"transport": httpx2.MockTransport(handle)}}
        with genai.Client(api_key="offline-test-fixture", vertexai=False, http_options=options) as client:
            with redirect_stdout(io.StringIO()):
                interaction = signal.interact(client, args, "测试请求")
        self.assertEqual(len(requests), 1)
        request = json.loads(requests[0].content)
        self.assertEqual(request["model"], "gemini-4-neon")
        self.assertEqual(request["generation_config"], {"thinking_level": "high"})
        self.assertEqual(request["tools"], [{"type": "google_search"}])
        self.assertEqual(request["response_format"], signal.RESPONSE_FORMAT)
        self.assertEqual(interaction.output_text, text)
        searched, citations = signal.search_evidence(interaction)
        self.assertTrue(searched)
        self.assertIn(signal.url_key(SOURCE_URL), citations)
