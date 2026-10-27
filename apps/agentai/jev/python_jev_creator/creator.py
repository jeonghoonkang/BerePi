"""Local AST analysis and non-destructive project generation (Python 3.9+)."""
import ast
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tokenize

IGNORED = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache'}
HELPER = '_python_jev_creator_decide'


@dataclass
class Candidate:
    file: str
    line: int
    column: int
    expression: str
    names: list
    question: str
    reason: str


@dataclass
class Analysis:
    source: Path
    root: Path
    output: Path
    files: list
    hashes: dict
    candidates: list


def read_source(path):
    with tokenize.open(str(path)) as stream:
        return stream.read(), stream.encoding


def inventory(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('링크는 지원하지 않습니다: ' + str(path))
    # Python 3.9 on Windows: junctions are reparse points too.
    if getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ValueError('재분석 지점은 지원하지 않습니다: ' + str(path))
    if path.is_file():
        return [path]
    result = []
    for child in sorted(path.iterdir()):
        if child.name not in IGNORED:
            result.extend(inventory(child))
    return result


def analyze(value):
    path = Path(value.strip().strip('"')).expanduser().absolute()
    if not path.exists():
        raise ValueError('입력 경로가 존재하지 않습니다.')
    files = inventory(path)
    if path.is_file() and path.suffix.lower() != '.py':
        raise ValueError('Python 파일 또는 프로젝트 폴더를 선택하세요.')
    root = path if path.is_dir() else path.parent
    output = root.with_name(root.name + 'jev')
    if not root.name:
        raise ValueError('드라이브 루트는 선택할 수 없습니다.')
    hashes, candidates = {}, []
    python_count = 0
    allowed = (ast.Expression, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Name,
               ast.Load, ast.Constant, ast.cmpop, ast.boolop, ast.Not, ast.Tuple, ast.List)
    for file in files:
        if file.suffix.lower() != '.py':
            continue
        python_count += 1
        relative = file.relative_to(root).as_posix()
        source, _ = read_source(file)
        hashes[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
        tree = ast.parse(source, filename=str(file))
        if HELPER in source:
            raise ValueError('이미 적용되었거나 지원 함수 이름이 충돌합니다: ' + relative)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.If, ast.IfExp)):
                continue
            test = node.test
            if not all(isinstance(n, allowed) for n in ast.walk(test)):
                continue
            names = sorted({n.id for n in ast.walk(test) if isinstance(n, ast.Name)})
            if not names:
                continue
            expression = ast.get_source_segment(source, test)
            semantic = any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                           for n in ast.walk(test))
            candidates.append(Candidate(relative, test.lineno, test.col_offset,
                expression, names,
                '주어진 변수의 의미와 문맥을 고려할 때 다음 조건의 의도에 해당합니까? ' + expression,
                '문자열 기반 분류·라우팅 후보' if semantic else
                '일반 조건식 후보: 수치·권한·정확성 조건은 기존 로직 유지 권장'))
    if not python_count:
        raise ValueError('Python 파일이 없습니다.')
    candidates.sort(key=lambda c: (c.file, c.line, c.column))
    return Analysis(path, root, output, files, hashes, candidates)


def transform(source, selected, helper_source):
    tree = ast.parse(source)
    conditions = {(n.test.lineno, n.test.col_offset): n.test for n in ast.walk(tree)
                  if isinstance(n, (ast.If, ast.IfExp))}
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def offset(line, byte_column):
        return offsets[line - 1] + len(lines[line - 1].encode('utf-8')[:byte_column].decode('utf-8'))

    edits = []
    for c in selected:
        if not c.question.strip():
            raise ValueError('판단 질문을 입력하세요.')
        node = conditions[(c.line, c.column)]
        state = '{' + ', '.join(repr(n) + ': ' + n for n in c.names) + '}'
        replacement = '{}(({}), {}, {})'.format(
            HELPER, c.expression, state, ascii(c.question))
        edits.append((offset(node.lineno, node.col_offset),
                      offset(node.end_lineno, node.end_col_offset), replacement))
    # Nested conditions can overlap, e.g. an if-expression inside an if test.
    ordered = sorted(edits)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('중첩된 조건은 하나만 선택하세요.')
    insertion_line = 0
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        insertion_line = body.pop(0).end_lineno
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            insertion_line = node.end_lineno
        else:
            break
    # Insert before first statement, preserving shebang, encoding and comments.
    if insertion_line == 0 and tree.body:
        insertion_line = tree.body[0].lineno - 1
    edits.append((offsets[insertion_line], offsets[insertion_line], '\n' + helper_source + '\n'))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    compile(source, '<jev-generated>', 'exec')
    return source


def generate(analysis, selected):
    if not selected:
        raise ValueError('적용할 판단 지점을 선택하세요.')
    if analysis.output.exists():
        raise ValueError('출력 폴더가 이미 존재합니다: ' + str(analysis.output))
    current = analyze(str(analysis.source))
    if current.hashes != analysis.hashes or current.files != analysis.files:
        raise ValueError('분석 이후 원본이 변경되었습니다. 다시 분석하세요.')
    keys = {(c.file, c.line, c.column) for c in analysis.candidates}
    if any((c.file, c.line, c.column) not in keys for c in selected):
        raise ValueError('분석 결과에 없는 후보입니다.')
    helper_source = Path(__file__).with_name('runtime_template.py').read_text(encoding='utf-8')
    stage = Path(tempfile.mkdtemp(prefix='.jev-', dir=str(analysis.output.parent)))
    try:
        for file in analysis.files:
            relative = file.relative_to(analysis.root)
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
        for relative in sorted({c.file for c in selected}):
            original, encoding = read_source(analysis.root / relative)
            result = transform(original, [c for c in selected if c.file == relative], helper_source)
            (stage / relative).write_bytes(result.encode(encoding))
        manifest = stage / 'jev_creator_manifest.json'
        if manifest.exists():
            raise ValueError('생성 보고서 파일 이름이 원본과 충돌합니다.')
        manifest.write_text(json.dumps({'source': str(analysis.source),
            'selected': [asdict(c) for c in selected],
            'runtime': 'Set TYPESAFE_API_KEY; optional JEV_ENABLED=0 disables API calls.'},
            ensure_ascii=False, indent=2), encoding='utf-8')
        if analysis.output.exists():
            raise ValueError('출력 폴더가 이미 존재합니다.')
        stage.rename(analysis.output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return analysis.output
