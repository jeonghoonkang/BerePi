import streamlit as st
import re
from pathlib import Path


def highlight_term(line: str, term: str) -> str:
    """Return HTML string with search term highlighted."""
    escaped = re.escape(term)
    pattern = re.compile(escaped, re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='background-color:yellow;color:red'>{m.group(0)}</span>", line)


def search_directory(directory: Path, term: str):
    """Yield tuples of (file_path, line_no, highlighted_line) for matches."""
    for path in directory.rglob('*.py'):
        if path.is_file():
            try:
                lines = path.read_text(encoding='utf-8').splitlines()
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(lines, 1):
                if term.lower() in line.lower():
                    yield path, i, highlight_term(line, term)


def main():
    st.title('Python Source Searcher')

    directory_input = st.text_input('Target directory', value='.')
    search_term = st.text_input('Text to search')

    if st.button('Search') and search_term and directory_input:
        directory = Path(directory_input)
        if not directory.is_dir():
            st.error(f'{directory} is not a directory')
            return
        results = list(search_directory(directory, search_term))
        if not results:
            st.info('No matches found.')
        else:
            for path, line_no, highlighted in results:
                st.markdown(f'**{path} : line {line_no}**', unsafe_allow_html=True)
                st.markdown(f'<pre>{highlighted}</pre>', unsafe_allow_html=True)
                st.markdown('---')


if __name__ == '__main__':
    main()
