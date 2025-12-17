"""CSV 필드 확인 및 시간 기반 그래프 생성 스크립트.

주요 기능
- CSV 파일의 필드명(컬럼명)을 출력합니다.
- 시간 컬럼과 선택한 수치 컬럼을 인자로 받아 그래프를 그립니다.
- 옵션으로 수치를 첫 번째 유효 값으로 정규화(normalize)할 수 있습니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd


EXAMPLE_USAGE = """\
실행 예시:
  # 필드만 확인
  python apps/csv/ev_field_check/run.py sample.csv --list-only

  # 시간 컬럼(time), 수치 컬럼(voltage, current) 그래프
  python apps/csv/ev_field_check/run.py sample.csv --time-field time --value-fields voltage current

  # 여러 CSV 파일 필드 확인 (통합)
  python apps/csv/ev_field_check/run.py --multi-file a.csv b.csv --list-only

  # 첫 유효 값을 기준으로 정규화하여 그래프
  python apps/csv/ev_field_check/run.py sample.csv --time-field time --value-fields voltage current --normalize

  # 필요한 컬럼만 추출하여 새 CSV 생성
  python apps/csv/ev_field_check/run.py sample.csv --extract time voltage current
"""


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSV 시간/수치 필드 시각화 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLE_USAGE,
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="읽을 CSV 파일 경로 (단일)",
    )
    parser.add_argument(
        "--multi-file",
        nargs="+",
        type=Path,
        help="여러 CSV 파일 경로 (공백 구분). 지정하면 csv_path 대신 사용됩니다.",
    )
    parser.add_argument(
        "--time-field",
        required=False,
        help="시간 데이터가 담긴 컬럼명",
    )
    parser.add_argument(
        "--value-fields",
        nargs="+",
        help="시간에 따라 시각화할 수치 컬럼명 (공백으로 구분해 여러 개 입력 가능)",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="각 수치 컬럼을 첫 번째 유효 값으로 나누어 1.0 기준으로 정규화",
    )
    parser.add_argument(
        "--extract",
        nargs="+",
        help="지정한 컬럼만 추출하여 새로운 CSV 파일로 저장",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="필드명만 출력하고 그래프는 그리지 않습니다",
    )
    return parser.parse_args(argv)


def load_csv(csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    return pd.read_csv(csv_path)


def load_multiple_csv(paths: Sequence[Path]):
    dataframes = []
    for path in paths:
        try:
            df = load_csv(path)
            dataframes.append(df)
        except Exception as exc:  # noqa: BLE001
            raise type(exc)(f"{path}: {exc}") from exc
    return dataframes


def print_fields(field_names: List[str]):
    print("\n=== CSV 필드 목록 ===")
    for column in field_names:
        print(column)
    print("===================\n")


def save_fields_to_txt(field_names: List[str], target_path: Path, *, filename: str | None = None) -> Path:
    output_path = (
        target_path.with_name(filename)
        if filename is not None
        else target_path.with_name(f"{target_path.stem}_fields.txt")
    )
    numbered = [f"{idx}: {name}" for idx, name in enumerate(field_names, start=1)]
    output_path.write_text("\n".join(numbered), encoding="utf-8")
    return output_path


def extract_fields_to_csv(
    df, fields: List[str], target_path: Path, *, filename: str | None = None
) -> tuple[Path, List[str]]:
    available = [field for field in fields if field in df.columns]
    missing = [field for field in fields if field not in df.columns]
    if not available:
        raise KeyError("지정한 컬럼 중 추출할 수 있는 컬럼이 없습니다.")

    output_path = (
        target_path.with_name(filename)
        if filename is not None
        else target_path.with_name(f"{target_path.stem}_extracted.csv")
    )
    df[available].to_csv(output_path, index=False)
    return output_path, missing


def normalize_columns(df, columns: List[str]):
    normalized = df.copy()
    for col in columns:
        series = normalized[col]
        first_valid = series.dropna().iloc[0] if not series.dropna().empty else None
        if first_valid is None or first_valid == 0:
            print(f"[경고] 컬럼 '{col}'을(를) 정규화할 수 없습니다 (첫 유효 값 없음 또는 0)")
            continue
        normalized[col] = series / first_valid
    return normalized


def plot_fields(df, time_field: str, value_fields: List[str]) -> None:
    import matplotlib.pyplot as plt

    if time_field not in df.columns:
        raise KeyError(f"시간 컬럼 '{time_field}'을(를) 찾을 수 없습니다.")

    missing = [field for field in value_fields if field not in df.columns]
    if missing:
        raise KeyError(f"존재하지 않는 수치 컬럼: {', '.join(missing)}")

    time_series = pd.to_datetime(df[time_field], errors="coerce")
    if time_series.isna().all():
        raise ValueError(f"시간 컬럼 '{time_field}'에서 유효한 시간을 찾을 수 없습니다.")

    plt.figure(figsize=(10, 6))
    for field in value_fields:
        plt.plot(time_series, df[field], label=field)

    plt.xlabel(time_field)
    plt.ylabel("값" if len(value_fields) == 1 else "값 (다중 컬럼)")
    plt.title("시간에 따른 수치 변화")
    plt.legend()
    plt.tight_layout()
    plt.grid(True)
    plt.show()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    file_paths: List[Path] = []
    if args.multi_file:
        file_paths = list(args.multi_file)
    elif args.csv_path:
        file_paths = [args.csv_path]
    else:
        print("CSV 파일 경로를 지정해주세요 (단일 파일 또는 --multi-file 사용).")
        return 1

    try:
        dataframes = load_multiple_csv(file_paths)
        df = pd.concat(dataframes, ignore_index=True, sort=False)
    except Exception as exc:  # noqa: BLE001
        print(f"CSV 로드 실패: {exc}")
        return 1

    field_names: List[str] = []
    seen = set()
    for frame in dataframes:
        for col in frame.columns:
            if col not in seen:
                seen.add(col)
                field_names.append(col)
    print_fields(field_names)

    if args.extract:
        try:
            target = file_paths[0]
            filename = None
            if len(file_paths) > 1:
                filename = f"{target.stem}_combined_extracted.csv"
            saved_path, missing = extract_fields_to_csv(df, args.extract, target, filename=filename)
            print(f"추출된 컬럼을 저장했습니다: {saved_path}")
            if missing:
                print(f"다음 컬럼은 존재하지 않아 제외되었습니다: {', '.join(missing)}")
        except Exception as exc:  # noqa: BLE001
            print(f"컬럼 추출 실패: {exc}")
            return 1
        return 0

    if args.list_only:
        try:
            target = file_paths[0]
            filename = None
            if len(file_paths) > 1:
                filename = f"{target.stem}_combined_fields.txt"
            saved_path = save_fields_to_txt(field_names, target, filename=filename)
            print(f"필드명을 파일로 저장했습니다: {saved_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"필드명 저장 실패: {exc}")
        return 0

    if not args.time_field or not args.value_fields:
        print("그래프를 그리려면 --time-field 와 --value-fields 를 모두 지정해야 합니다.")
        return 1

    plot_df = normalize_columns(df, args.value_fields) if args.normalize else df

    try:
        plot_fields(plot_df, args.time_field, args.value_fields)
    except Exception as exc:  # noqa: BLE001
        print(f"그래프 생성 실패: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
