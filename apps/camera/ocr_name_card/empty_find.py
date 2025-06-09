import json

# JSON 파일 열기
with open('./save_description/file_list.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# 결과를 저장할 리스트
empty_filepaths = []

# JSON 데이터 순회
for item in data:
    if (
        item.get('ocr', '') == '' and
        item.get('name', '') == '' and
        item.get('company', '') == '' and
        item.get('email', '') == ''
    ):
        empty_filepaths.append(item['original_filepath'])

# 결과를 txt 파일로 저장
with open('empty_filepaths.txt', 'w', encoding='utf-8') as out_file:
    for path in empty_filepaths:
        out_file.write(path + '\n')
