import copy
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from creator import analyze, generate


class App:
    def __init__(self, root):
        self.root, self.analysis = root, None
        self.selected, self.questions = set(), {}
        self.events = queue.Queue()
        self.active = None
        root.title('Python JEV Creator')
        root.geometry('1080x760')
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='저는 python code 를 jev 기능을 추가해 주는 소프트웨어 입니다.').pack(anchor='w')
        ttk.Label(frame, text='입력할 python code 경로를 아래 입력창에 넣어주세요').pack(anchor='w', pady=(12, 4))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.path = tk.StringVar()
        ttk.Entry(row, textvariable=self.path).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='파일 선택', command=self.pick_file).pack(side='left')
        ttk.Button(row, text='폴더 선택', command=self.pick_folder).pack(side='left')
        self.analyze_button = ttk.Button(row, text='분석', command=self.scan)
        self.analyze_button.pack(side='left')
        self.status = tk.StringVar(value='분석은 로컬에서 수행됩니다. Python 3.9 이상이 필요합니다.')
        ttk.Label(frame, textvariable=self.status, wraplength=1000).pack(anchor='w', pady=8)
        self.tree = ttk.Treeview(frame, columns=('on', 'file', 'line', 'reason'), show='headings', height=10)
        for key, title, width in [('on', '선택', 55), ('file', '파일', 300), ('line', '행', 55), ('reason', '제안 이유', 600)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, stretch=key in ('file', 'reason'))
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.show)
        self.tree.bind('<Double-1>', self.toggle)
        ttk.Button(frame, text='현재 후보 선택 / 해제', command=self.toggle).pack(anchor='w', pady=4)
        self.detail = tk.Text(frame, height=6, wrap='word', state='disabled')
        self.detail.pack(fill='x')
        ttk.Label(frame, text='Jev 판단 질문 (편집 후 다른 후보를 선택해도 자동 저장됩니다)').pack(anchor='w', pady=(6, 2))
        self.question = tk.Text(frame, height=3, wrap='word')
        self.question.pack(fill='x')
        ttk.Label(frame, text='선택한 조건의 변수 값이 실행 시 TypeSafe API로 전송됩니다. '
                  '권한·보안·정확한 수치 조건은 적용 전 검토하세요.', wraplength=1000).pack(anchor='w', pady=6)
        self.generate_button = ttk.Button(frame, text='선택한 지점에 Jev 코드 생성', command=self.create, state='disabled')
        self.generate_button.pack(anchor='e')
        root.after(100, self.poll)

    def pick_file(self):
        value = filedialog.askopenfilename(filetypes=[('Python', '*.py')])
        if value:
            self.path.set(value)

    def pick_folder(self):
        value = filedialog.askdirectory()
        if value:
            self.path.set(value)

    def save_question(self):
        if self.active is not None:
            self.questions[self.active] = self.question.get('1.0', 'end-1c')

    def show(self, event=None):
        self.save_question()
        items = self.tree.selection()
        if not items or self.analysis is None:
            return
        self.active = int(items[0])
        c = self.analysis.candidates[self.active]
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', '{}:{}\n원래 조건: {}\n전송할 변수: {}\n{}'.format(
            c.file, c.line, c.expression, ', '.join(c.names), c.reason))
        self.detail.configure(state='disabled')
        self.question.delete('1.0', 'end')
        self.question.insert('1.0', self.questions.get(self.active, c.question))

    def toggle(self, event=None):
        items = self.tree.selection()
        if not items:
            return
        index = int(items[0])
        if index in self.selected:
            self.selected.remove(index)
        else:
            self.selected.add(index)
        self.tree.set(str(index), 'on', '✓' if index in self.selected else '')

    def work(self, kind, action):
        self.analyze_button.configure(state='disabled')
        self.generate_button.configure(state='disabled')
        self.status.set('분석 중…' if kind == 'analysis' else '코드 생성 중…')
        def worker():
            try:
                self.events.put((kind, action(), None))
            except Exception as error:
                self.events.put((kind, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def scan(self):
        value = self.path.get()
        if not value.strip():
            messagebox.showerror('경로 오류', 'Python 코드 경로를 입력하세요.')
            return
        self.analysis, self.active = None, None
        self.selected.clear()
        self.questions.clear()
        self.tree.delete(*self.tree.get_children())
        self.work('analysis', lambda: analyze(value))

    def create(self):
        self.save_question()
        if self.analysis is None or not self.selected:
            messagebox.showinfo('후보 선택', '적용할 판단 지점을 선택하세요.')
            return
        if self.path.get().strip().strip('"') != str(self.analysis.source) and self.path.get().strip().strip('"') != str(self.analysis.source.as_posix()):
            # Relative input is valid too; compare normalized paths.
            from pathlib import Path
            if Path(self.path.get().strip().strip('"')).expanduser().absolute() != self.analysis.source:
                messagebox.showerror('경로 변경', '경로가 변경되었습니다. 다시 분석하세요.')
                return
        selected = [copy.deepcopy(self.analysis.candidates[i]) for i in sorted(self.selected)]
        for i, c in zip(sorted(self.selected), selected):
            c.question = self.questions.get(i, c.question)
        analysis = self.analysis
        self.work('generated', lambda: generate(analysis, selected))

    def poll(self):
        try:
            while True:
                kind, value, error = self.events.get_nowait()
                self.analyze_button.configure(state='normal')
                if error:
                    self.status.set('실패: ' + error)
                    messagebox.showerror('처리 오류', error)
                elif kind == 'analysis':
                    self.analysis = value
                    for i, c in enumerate(value.candidates):
                        self.tree.insert('', 'end', iid=str(i), values=('', c.file, c.line, c.reason))
                    self.status.set('후보 {}개 / 생성 위치: {}'.format(len(value.candidates), value.output))
                else:
                    self.status.set('생성 완료: ' + str(value))
                    messagebox.showinfo('완료', '생성 위치: ' + str(value) + '\n실행 전에 TYPESAFE_API_KEY 환경 변수를 설정하세요.')
                if self.analysis and self.analysis.candidates:
                    self.generate_button.configure(state='normal')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
