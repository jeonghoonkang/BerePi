#!/usr/bin/env python3
"""Tkinter GUI for the BerePi LocalSend sender."""

from pathlib import Path
import queue
import socket
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import localsend

try:
    from PIL import Image, ImageGrab, ImageTk
except ImportError:
    Image = ImageGrab = ImageTk = None


class LocalSendApp:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.events = queue.Queue()
        self.paths = []
        self.peers = []
        self.clipboard_image = None
        self.image_preview = None
        self.controls = []
        root.title('BerePi LocalSend')
        root.geometry('820x720')
        root.minsize(680, 620)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.host = tk.StringVar()
        self.port = tk.StringVar(value=str(localsend.PORT))
        self.protocol = tk.StringVar(value='https')
        self.alias = tk.StringVar(value='BerePi-' + socket.gethostname())
        self.pin = tk.StringVar()
        self.timeout = tk.StringVar(value='120')
        self.status = tk.StringVar(value='대상 IP를 입력하거나 주변 기기를 검색하세요.')

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='LocalSend 전송', font=('', 18, 'bold')).grid(
            row=0, column=0, columnspan=4, sticky='w', pady=(0, 12))
        self.entry(frame, '대상 IP / 호스트', self.host, 1)
        self.button(frame, '주변 기기 검색', self.search).grid(row=1, column=2, padx=8)
        self.devices = ttk.Combobox(frame, state='readonly')
        self.devices.grid(row=2, column=1, columnspan=2, sticky='ew', pady=5)
        self.devices.bind('<<ComboboxSelected>>', self.select_peer)
        self.controls.append((self.devices, 'readonly'))
        ttk.Label(frame, text='검색 결과').grid(row=2, column=0, sticky='w')
        options = ttk.Frame(frame)
        options.grid(row=3, column=1, columnspan=2, sticky='ew', pady=5)
        for label, variable, width in [('포트', self.port, 7), ('PIN', self.pin, 10),
                                       ('대기(초)', self.timeout, 6)]:
            ttk.Label(options, text=label).pack(side='left', padx=(0, 5))
            widget = ttk.Entry(options, textvariable=variable, width=width,
                               show='*' if label == 'PIN' else '')
            widget.pack(side='left', padx=(0, 12))
            self.controls.append((widget, 'normal'))
        protocol = ttk.Combobox(options, textvariable=self.protocol,
                                values=['https', 'http'], state='readonly', width=7)
        protocol.pack(side='left')
        self.controls.append((protocol, 'readonly'))
        self.entry(frame, '송신 기기 이름', self.alias, 4)

        self.tabs = ttk.Notebook(frame)
        self.tabs.grid(row=5, column=0, columnspan=3, sticky='nsew', pady=12)
        frame.rowconfigure(5, weight=1)
        files_tab = ttk.Frame(self.tabs, padding=10)
        text_tab = ttk.Frame(self.tabs, padding=10)
        image_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(files_tab, text='파일 / 폴더')
        self.tabs.add(text_tab, text='클립보드 텍스트')
        self.tabs.add(image_tab, text='클립보드 이미지')
        toolbar = ttk.Frame(files_tab)
        toolbar.pack(fill='x')
        for label, callback in [('파일 선택', self.pick_files), ('폴더 선택', self.pick_folder),
                                ('선택 제거', self.remove_files), ('모두 지우기', self.clear_files)]:
            self.button(toolbar, label, callback).pack(side='left', padx=(0, 6))
        self.file_list = tk.Listbox(files_tab, selectmode='extended', height=8)
        self.file_list.pack(fill='both', expand=True, pady=8)
        scroll = ttk.Scrollbar(files_tab, orient='horizontal', command=self.file_list.xview)
        scroll.pack(fill='x')
        self.file_list.configure(xscrollcommand=scroll.set)
        self.button(text_tab, '클립보드 가져오기', self.paste_clipboard).pack(anchor='w')
        ttk.Label(text_tab, text='가져온 내용을 확인·수정한 뒤 전송하세요. UTF-8 clipboard.txt로 전송됩니다.').pack(
            anchor='w', pady=6)
        self.text = tk.Text(text_tab, wrap='word', height=8, undo=True)
        self.text.pack(fill='both', expand=True)
        image_toolbar = ttk.Frame(image_tab)
        image_toolbar.pack(fill='x')
        self.button(image_toolbar, '이미지 가져오기', self.paste_image).pack(side='left')
        self.button(image_toolbar, '이미지 지우기', self.clear_image).pack(side='left', padx=8)
        self.image_info = ttk.Label(image_tab, text='화면 캡처 또는 이미지를 복사한 뒤 가져오세요. clipboard.png로 전송됩니다.')
        self.image_info.pack(anchor='w', pady=6)
        self.image_label = ttk.Label(image_tab, anchor='center')
        self.image_label.pack(fill='both', expand=True)
        ttk.Label(frame, text='현재 선택된 탭의 내용만 전송합니다. 수신 LocalSend 앱에서 승인해 주세요.').grid(
            row=6, column=0, columnspan=3, sticky='w')
        self.button(frame, '전송', self.start_send).grid(row=7, column=2, sticky='e', pady=8)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.grid(row=8, column=0, columnspan=3, sticky='ew')
        ttk.Label(frame, textvariable=self.status, wraplength=750).grid(
            row=9, column=0, columnspan=3, sticky='w', pady=8)
        self.logs = tk.Text(frame, height=6, state='disabled', wrap='word')
        self.logs.grid(row=10, column=0, columnspan=3, sticky='ew')
        root.after(100, self.poll)

    def button(self, parent, label, callback):
        widget = ttk.Button(parent, text=label, command=callback)
        self.controls.append((widget, 'normal'))
        return widget

    def entry(self, parent, label, variable, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12))
        widget = ttk.Entry(parent, textvariable=variable)
        widget.grid(row=row, column=1, sticky='ew', pady=5)
        self.controls.append((widget, 'normal'))

    def add_paths(self, paths):
        for path in paths:
            if path not in self.paths:
                self.paths.append(path)
                self.file_list.insert('end', path)

    def pick_files(self):
        self.add_paths(filedialog.askopenfilenames(parent=self.root, title='전송할 파일 선택'))

    def pick_folder(self):
        path = filedialog.askdirectory(parent=self.root, title='전송할 폴더 선택')
        if path:
            self.add_paths([path])

    def remove_files(self):
        for index in reversed(self.file_list.curselection()):
            del self.paths[index]
            self.file_list.delete(index)

    def clear_files(self):
        self.paths.clear()
        self.file_list.delete(0, 'end')

    def paste_clipboard(self):
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showinfo('클립보드', '클립보드에 텍스트가 없습니다. 이미지는 클립보드 이미지 탭에서 가져오세요.')
            return
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)

    def clear_image(self):
        self.clipboard_image = None
        self.image_preview = None
        self.image_label.configure(image='')
        self.image_info.configure(text='이미지를 복사한 뒤 가져오세요. clipboard.png로 전송됩니다.')

    def paste_image(self):
        # Clear the previous snapshot so a failed paste cannot send an older image.
        self.clear_image()
        if ImageGrab is None:
            messagebox.showerror('이미지 클립보드',
                                 'Pillow가 필요합니다. 실행 중인 Python으로 다음 명령을 실행하세요:\n'
                                 'python -m pip install -r apps/tools/localsend/requirements.txt')
            return
        try:
            image = ImageGrab.grabclipboard()
            if not isinstance(image, Image.Image):
                messagebox.showinfo('이미지 클립보드',
                                    '클립보드에 이미지가 없습니다. 캡처나 이미지 복사를 사용하세요.\n'
                                    '복사한 파일은 파일 / 폴더 탭에서 선택하세요.')
                return
            snapshot = image.copy()
            preview = snapshot.copy()
            preview.thumbnail((600, 180))
            self.image_preview = ImageTk.PhotoImage(preview, master=self.root)
            self.image_label.configure(image=self.image_preview)
            self.clipboard_image = snapshot
            self.image_info.configure(text=f'{snapshot.width} × {snapshot.height} px — clipboard.png (원본 크기 전송)')
        except Exception as exc:
            self.clear_image()
            messagebox.showerror('이미지 클립보드', f'이미지를 가져오지 못했습니다: {exc}')

    def select_peer(self, _event=None):
        index = self.devices.current()
        if index >= 0:
            peer = self.peers[index]
            self.host.set(peer['host'])
            self.port.set(str(peer['port']))
            self.protocol.set(peer['protocol'])

    def run(self, work, status):
        if self.busy:
            return
        self.busy = True
        for widget, _ in self.controls:
            widget.configure(state='disabled')
        self.status.set(status)
        self.progress.start()

        def worker():
            try:
                work()
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('done', None))

        threading.Thread(target=worker, daemon=True).start()

    def search(self):
        info = localsend.sender_info(self.alias.get().strip() or 'BerePi')

        def work():
            peers = localsend.discover(info)
            self.events.put(('peers', peers))

        self.run(work, '주변 기기 검색 중…')

    def start_send(self):
        host = self.host.get().strip()
        try:
            port, timeout = int(self.port.get()), float(self.timeout.get())
            if not host or '://' in host or '/' in host or any(c.isspace() for c in host):
                raise ValueError('대상 IP 또는 호스트 이름을 입력하세요. URL은 입력하지 마세요.')
            if not 1 <= port <= 65535 or not 0 < timeout < float('inf'):
                raise ValueError('포트는 1~65535, 대기 시간은 양수로 입력하세요.')
            mode = self.tabs.index(self.tabs.select())
            text_mode = mode == 1
            image_mode = mode == 2
            text = self.text.get('1.0', 'end-1c') if text_mode else None
            image = self.clipboard_image.copy() if image_mode and self.clipboard_image is not None else None
            paths = list(self.paths)
            if text_mode and not text:
                raise ValueError('클립보드 텍스트를 가져오거나 입력하세요.')
            if image_mode and image is None:
                raise ValueError('클립보드 이미지를 먼저 가져오세요.')
            if mode == 0 and not paths:
                raise ValueError('전송할 파일이나 폴더를 선택하세요.')
        except ValueError as exc:
            messagebox.showerror('입력 확인', str(exc))
            return
        protocol, pin = self.protocol.get(), self.pin.get()
        info = localsend.sender_info(self.alias.get().strip() or 'BerePi')

        def work():
            with tempfile.TemporaryDirectory(prefix='berepi-localsend-') as folder:
                if text_mode:
                    path = Path(folder) / 'clipboard.txt'
                    path.write_bytes(text.encode('utf-8'))
                    selected = [str(path)]
                elif image_mode:
                    path = Path(folder) / 'clipboard.png'
                    image.save(path, format='PNG')
                    selected = [str(path)]
                else:
                    selected = paths
                files = localsend.collect_files(selected)
                self.events.put(('log', f'{host}:{port} — {len(files)}개 파일, 수신 승인 대기 중'))
                count = localsend.send(host, port, protocol, info, files, pin or None,
                                       timeout, log=lambda line: self.events.put(('log', line)))
                self.events.put(('success', f'완료: {count}/{len(files)}개 파일 전송'))

        self.run(work, '전송 준비 / 수신 승인 대기 중…')

    def log(self, value):
        self.logs.configure(state='normal')
        self.logs.insert('end', value + '\n')
        self.logs.see('end')
        self.logs.configure(state='disabled')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'done':
                    self.busy = False
                    self.progress.stop()
                    for widget, state in self.controls:
                        widget.configure(state=state)
                elif kind == 'peers':
                    self.peers = value
                    self.devices.configure(values=[f'{p["alias"]} ({p["host"]}:{p["port"]})' for p in value])
                    self.devices.set('')
                    self.status.set(f'{len(value)}개 기기 발견. 선택하거나 IP를 직접 입력하세요.')
                elif kind == 'error':
                    self.status.set('실패: ' + value)
                    self.log('실패: ' + value)
                    messagebox.showerror('LocalSend 오류', value)
                else:
                    self.log(value)
                    self.status.set(value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('작업 진행 중', '작업이 끝난 뒤 창을 닫아 주세요. 네트워크 응답은 설정한 대기 시간까지 기다립니다.')
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    LocalSendApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
