import json
import os
import tempfile
import unittest
from unittest import mock

import blocker


class HostsParsingTests(unittest.TestCase):
    def test_parses_hosts_and_plain_domain_formats(self):
        content = """
        # comment
        127.0.0.1 example.com www.example.com
        0.0.0.0 ads.example.net # inline comment
        plain.example.org
        127.0.0.1 localhost
        invalid_value
        """

        self.assertEqual(
            blocker.parse_hosts_content(content),
            ["ads.example.net", "example.com", "plain.example.org", "www.example.com"],
        )

    def test_normalizes_urls_idn_and_rejects_unsafe_values(self):
        self.assertEqual(blocker.normalize_domain("https://WWW.Example.com/path"), "www.example.com")
        self.assertEqual(blocker.normalize_domain("*.café.example"), "xn--caf-dma.example")
        self.assertIsNone(blocker.normalize_domain("localhost"))
        self.assertIsNone(blocker.normalize_domain("127.0.0.1"))
        self.assertIsNone(blocker.normalize_domain("bad domain.example"))

    def test_process_names_reject_taskkill_wildcards_and_paths(self):
        self.assertEqual(blocker.normalize_process_name("Example"), "Example.exe")
        self.assertEqual(blocker.normalize_process_name("my app.exe"), "my app.exe")
        self.assertIsNone(blocker.normalize_process_name("*.exe"))
        self.assertIsNone(blocker.normalize_process_name(r"C:\\Windows\\notepad.exe"))


class HostsFileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.hosts_path = os.path.join(self.temp_dir.name, "hosts")
        with open(self.hosts_path, "w", encoding="utf-8") as handle:
            handle.write("127.0.0.1 localhost\n10.0.0.5 internal.example\n")
        self.original_hosts_path = blocker.HOSTS_PATH
        blocker.HOSTS_PATH = self.hosts_path

    def tearDown(self):
        blocker.HOSTS_PATH = self.original_hosts_path
        self.temp_dir.cleanup()

    @mock.patch("blocker.flush_dns")
    def test_block_is_idempotent_and_preserves_unmanaged_entries(self, flush_dns):
        blocker.block_sites(["Example.com", "example.com", "invalid value"])
        with open(self.hosts_path, "r", encoding="utf-8") as handle:
            first = handle.read()

        blocker.block_sites(["example.com"])
        with open(self.hosts_path, "r", encoding="utf-8") as handle:
            second = handle.read()

        self.assertEqual(first, second)
        self.assertIn("10.0.0.5 internal.example", second)
        self.assertEqual(second.count("127.0.0.1 example.com"), 1)
        self.assertTrue(os.path.exists(self.hosts_path + ".website-blocker-backup"))
        flush_dns.assert_called_once()

    @mock.patch("blocker.flush_dns")
    def test_unblock_removes_only_managed_section(self, flush_dns):
        blocker.block_sites(["example.com"])
        blocker.unblock_sites()
        with open(self.hosts_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertNotIn(blocker.BLOCK_MARKER_START, content)
        self.assertNotIn("example.com", content)
        self.assertIn("internal.example", content)
        self.assertEqual(flush_dns.call_count, 2)

    def test_unterminated_marker_is_preserved(self):
        content = "before\n{}\nkeep-this\n".format(blocker.BLOCK_MARKER_START)
        self.assertEqual(blocker.remove_blocker_entries(content), content.rstrip("\n"))

    @mock.patch("blocker.flush_dns")
    def test_incomplete_marker_never_modifies_hosts_file(self, flush_dns):
        original = "before\n{}\nkeep-this\n".format(blocker.BLOCK_MARKER_START)
        with open(self.hosts_path, "w", encoding="utf-8") as handle:
            handle.write(original)

        with self.assertRaises(RuntimeError):
            blocker.block_sites(["example.com"])
        with open(self.hosts_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)
        flush_dns.assert_not_called()

    @mock.patch("blocker.time.sleep")
    @mock.patch("blocker.socket.getaddrinfo")
    def test_live_verification_retries_until_domain_resolves_locally(self, getaddrinfo, sleep):
        getaddrinfo.side_effect = [
            [(None, None, None, None, ("93.184.216.34", 443))],
            [(None, None, None, None, ("127.0.0.1", 443))],
        ]

        verified = blocker.verify_blocked_domains(["example.com"], attempts=2)

        self.assertEqual(verified, ["example.com"])
        sleep.assert_called_once()

    @mock.patch("blocker.time.sleep")
    @mock.patch("blocker.socket.getaddrinfo")
    def test_live_verification_fails_on_public_resolution(self, getaddrinfo, _sleep):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 443))]

        with self.assertRaisesRegex(RuntimeError, "DNS blocking verification failed"):
            blocker.verify_blocked_domains(["example.com"], attempts=2)


class HostsSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.originals = {
            "CONFIG_FILE": blocker.CONFIG_FILE,
            "HOSTS_LIST_DIR": blocker.HOSTS_LIST_DIR,
            "HOSTS_CACHE_DIR": blocker.HOSTS_CACHE_DIR,
        }
        blocker.CONFIG_FILE = os.path.join(self.temp_dir.name, "config.json")
        blocker.HOSTS_LIST_DIR = os.path.join(self.temp_dir.name, "hosts")
        blocker.HOSTS_CACHE_DIR = os.path.join(blocker.HOSTS_LIST_DIR, "cache")
        os.makedirs(blocker.HOSTS_CACHE_DIR)

    def tearDown(self):
        for key, value in self.originals.items():
            setattr(blocker, key, value)
        self.temp_dir.cleanup()

    def test_loads_only_enabled_managed_sources_plus_manual_files(self):
        enabled = {"name": "enabled", "url": "https://example.com/enabled.txt", "enabled": True}
        disabled = {"name": "disabled", "url": "https://example.com/disabled.txt", "enabled": False}
        config = {"blocked_sites": ["custom.example"], "blocked_urls": [], "blocked_apps": [], "hosts_sources": [enabled, disabled]}
        with open(blocker.CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        with open(os.path.join(blocker.HOSTS_LIST_DIR, "manual.hosts"), "w", encoding="utf-8") as handle:
            handle.write("0.0.0.0 manual.example\n")
        with open(blocker._source_cache_path(enabled), "w", encoding="utf-8") as handle:
            handle.write("enabled.example\n")
        with open(blocker._source_cache_path(disabled), "w", encoding="utf-8") as handle:
            handle.write("disabled.example\n")

        self.assertEqual(
            blocker.load_blocked_domains(),
            ["custom.example", "enabled.example", "manual.example"],
        )

    def test_cache_filename_cannot_escape_cache_directory(self):
        source = {"name": "../../escape", "url": "https://example.com/list.txt"}
        path = os.path.abspath(blocker._source_cache_path(source))
        self.assertEqual(os.path.commonpath([path, blocker.HOSTS_CACHE_DIR]), blocker.HOSTS_CACHE_DIR)

    def test_save_full_config_writes_all_supported_keys(self):
        blocker.save_full_config({"blocked_sites": ["example.com"]})
        with open(blocker.CONFIG_FILE, "r", encoding="utf-8") as handle:
            saved = json.load(handle)

        self.assertEqual(saved["blocked_sites"], ["example.com"])
        self.assertIn("blocked_urls", saved)
        self.assertIn("blocked_apps", saved)
        self.assertIn("hosts_sources", saved)


if __name__ == "__main__":
    unittest.main()
