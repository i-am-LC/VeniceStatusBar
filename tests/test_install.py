from pathlib import Path
import subprocess
import tempfile
import unittest

from install import install


class InstallTests(unittest.TestCase):
    def test_portable_install(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, entry = install(source, root / 'data with spaces $cash %value', root / 'config')
            self.assertEqual(script.read_bytes(), (source / 'venice_indicator.py').read_bytes())
            self.assertEqual(script.stat().st_mode & 0o777, 0o755)
            self.assertNotIn('@SCRIPT_PATH@', entry.read_text())
            self.assertNotIn('/home/lsc/', entry.read_text())
            subprocess.run(['desktop-file-validate', str(entry)], check=True)
            # Updating the application must leave saved credentials alone.
            key = root / 'config/venice-indicator/config.json'
            key.parent.mkdir()
            key.write_text('{"api_key": "dummy-test-key"}')
            install(source, root / 'data with spaces $cash %value', root / 'config')
            self.assertEqual(key.read_text(), '{"api_key": "dummy-test-key"}')
