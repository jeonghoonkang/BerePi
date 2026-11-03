import queue
import gc
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from localsend_gui import LocalSendApp, Image


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'Graphical display unavailable: {exc}')
        self.root.withdraw()
        self.app = LocalSendApp(self.root)
        self.addCleanup(self.cleanup_gui)
        self.app.host.set('192.168.0.25')

    def cleanup_gui(self):
        self.root.destroy()
        del self.app
        del self.root
        # Tk objects must be finalized on the main thread, before later workers run.
        gc.collect()

    def wait_worker(self):
        deadline = time.monotonic() + 3
        messages = []
        while time.monotonic() < deadline:
            try:
                event = self.app.events.get(timeout=.1)
            except queue.Empty:
                continue
            messages.append(event)
            if event[0] == 'done':
                break
        self.assertEqual(messages[-1][0], 'done')
        self.assertFalse([m for m in messages if m[0] == 'error'], messages)
        return messages

    def test_clipboard_text_snapshot_and_cleanup(self):
        self.root.clipboard_clear()
        self.root.clipboard_append('한글 clipboard\nsecond line')
        self.app.paste_clipboard()
        self.app.tabs.select(1)
        captured = []

        def send(host, port, protocol, info, files, pin, timeout, log):
            path, metadata = next(iter(files.values()))
            captured.append(path)
            self.assertEqual(path.read_bytes(), '한글 clipboard\nsecond line'.encode('utf-8'))
            self.assertEqual(metadata['fileName'], 'clipboard.txt')
            self.assertEqual(host, '192.168.0.25')
            log('uploaded')
            return 1

        with patch('localsend_gui.localsend.send', side_effect=send):
            self.app.start_send()
            messages = self.wait_worker()
        self.assertTrue(any(m[0] == 'success' for m in messages))
        self.assertFalse(captured[0].exists())

    def test_file_selection_and_peer_target(self):
        self.app.peers = [dict(host='192.168.0.26', port=53318,
                               protocol='http', alias='Mac')]
        self.app.devices.configure(values=['Mac'])
        self.app.devices.current(0)
        self.app.select_peer()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sample.txt'
            path.write_text('file data', encoding='utf-8')
            self.app.add_paths([str(path), str(path)])
            self.assertEqual(len(self.app.paths), 1)

            def send(host, port, protocol, info, files, pin, timeout, log):
                self.assertEqual((host, port, protocol), ('192.168.0.26', 53318, 'http'))
                self.assertEqual(next(iter(files.values()))[0].read_text(), 'file data')
                return 1

            with patch('localsend_gui.localsend.send', side_effect=send):
                self.app.start_send()
                self.wait_worker()

    def test_invalid_target_does_not_start_worker(self):
        self.app.host.set('https://192.168.0.25')
        with patch('localsend_gui.messagebox.showerror') as error:
            self.app.start_send()
        error.assert_called_once()
        self.assertFalse(self.app.busy)

    @unittest.skipIf(Image is None, 'Pillow is not installed')
    def test_clipboard_image_png_snapshot_and_cleanup(self):
        original = Image.new('RGBA', (900, 400), (20, 40, 60, 128))
        with patch('localsend_gui.ImageGrab.grabclipboard', return_value=original):
            self.app.paste_image()
        self.assertEqual(self.app.clipboard_image.size, (900, 400))
        self.assertLessEqual(self.app.image_preview.width(), 600)
        self.assertLessEqual(self.app.image_preview.height(), 180)
        original.paste((255, 0, 0, 255), (0, 0, 900, 400))
        self.app.tabs.select(2)
        captured = []

        def send(host, port, protocol, info, files, pin, timeout, log):
            path, metadata = next(iter(files.values()))
            captured.append(path)
            self.assertEqual(metadata['fileName'], 'clipboard.png')
            self.assertEqual(metadata['fileType'], 'image/png')
            with Image.open(path) as png:
                self.assertEqual(png.size, (900, 400))
                self.assertEqual(png.getpixel((0, 0)), (20, 40, 60, 128))
            return 1

        with patch('localsend_gui.localsend.send', side_effect=send):
            self.app.start_send()
            self.wait_worker()
        self.assertFalse(captured[0].exists())

    @unittest.skipIf(Image is None, 'Pillow is not installed')
    def test_non_image_clipboard_clears_old_image(self):
        self.app.clipboard_image = Image.new('RGB', (2, 2))
        for value in (None, ['copied-file.png']):
            with patch('localsend_gui.ImageGrab.grabclipboard', return_value=value), \
                    patch('localsend_gui.messagebox.showinfo') as info:
                self.app.paste_image()
            info.assert_called_once()
            self.assertIsNone(self.app.clipboard_image)
        self.app.tabs.select(2)
        with patch('localsend_gui.messagebox.showerror') as error:
            self.app.start_send()
        error.assert_called_once()
        self.assertFalse(self.app.busy)

    def test_missing_pillow_explains_installation(self):
        with patch('localsend_gui.ImageGrab', None), \
                patch('localsend_gui.messagebox.showerror') as error:
            self.app.paste_image()
        self.assertIn('pip install', error.call_args[0][1])

    @unittest.skipIf(Image is None, 'Pillow is not installed')
    def test_clipboard_backend_error(self):
        with patch('localsend_gui.ImageGrab.grabclipboard', side_effect=OSError('clipboard busy')), \
                patch('localsend_gui.messagebox.showerror') as error:
            self.app.paste_image()
        self.assertIn('clipboard busy', error.call_args[0][1])
        self.assertIsNone(self.app.clipboard_image)


if __name__ == '__main__':
    unittest.main()
