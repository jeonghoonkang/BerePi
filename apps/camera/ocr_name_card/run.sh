#!/bin/bash

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    python3 run_ocr_name_card.py {scan_image_path} {save_description_path}
    exit 0
fi

if [ -f 'info.ini' ]
then

    keyword=$1
    source info.ini

    echo ""
    echo ">>===================================================="
    echo "실행 관련 주요 정보(run.sh)"
    echo "scan_image_path       : "$scan_image_path : from info.ini
    echo "save_description_path : "$save_description_path : from info.ini
    echo "====================================================<<"

    #arg         [0]                   [1]         [2]
    time python3 run_ocr_name_card.py  $dir_path   $save_path
    echo " *** end script run for PYTHON *** "
    exit 0
else
    echo "info.ini 파일이 존재하지 않습니다. no ini file"
    echo "info.ini 파일을 생성해 주세요. should make info.ini file"
    exit 0
fi