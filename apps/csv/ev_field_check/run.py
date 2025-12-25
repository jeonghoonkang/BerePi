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

  # 출력 파일 이름을 지정해 추출
  python apps/csv/ev_field_check/run.py sample.csv --extract time voltage --extract-output filtered.csv

  # 조건을 걸어 필요한 컬럼만 추출 (예: status가 OK이고 temp > 30)
  python apps/csv/ev_field_check/run.py sample.csv --extract time temp status \
    --extract-filter "status=OK" --extract-filter "temp>30"
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
        "--extract-output",
        type=str,
        help="추출 결과를 저장할 CSV 파일 이름을 지정합니다",
    )
    parser.add_argument(
        "--drop-non-numeric",
        action="store_true",
        help="추출 시 숫자가 아닌 값이 포함된 컬럼을 자동으로 제외",
    )
    parser.add_argument(
        "--extract-filter",
        action="append",
        metavar="FIELD[OP]VALUE",
        help="추출 전에 필터를 적용합니다 (예: status=OK, temp>30, voltage<3.6). 여러 번 지정 가능",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="총 행 수, 필드 개수, 시간 컬럼 표시를 포함한 상세 정보를 출력",
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


def print_details(field_names: List[str], df, time_field: str | None):
    print("\n=== CSV 상세 정보 ===")
    print(f"총 행 수: {len(df)}")
    print(f"필드 개수: {len(field_names)}")
    if time_field:
        presence = "(존재)" if time_field in field_names else "(미발견)"
        print(f"지정한 시간 컬럼: {time_field} {presence}")
    else:
        print("지정한 시간 컬럼: 없음")

    print("필드 목록 (시간 컬럼은 * 표시):")
    for column in field_names:
        prefix = "* " if time_field and column == time_field else "- "
        print(f"{prefix}{column}")
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


def find_non_numeric_fields(df, fields: List[str]) -> List[str]:
    non_numeric_fields: List[str] = []
    for field in fields:
        if field not in df.columns:
            continue
        series = df[field]
        numeric = pd.to_numeric(series, errors="coerce")
        has_non_numeric = (numeric.isna() & series.notna()).any()
        if has_non_numeric:
            non_numeric_fields.append(field)
    return non_numeric_fields


def extract_fields_to_csv(
    df,
    fields: List[str],
    target_path: Path,
    *,
    filename: str | None = None,
    drop_non_numeric: bool = False,
) -> tuple[Path, List[str], List[str]]:
    available = [field for field in fields if field in df.columns]
    missing = [field for field in fields if field not in df.columns]
    if not available:
        raise KeyError("지정한 컬럼 중 추출할 수 있는 컬럼이 없습니다.")

    non_numeric_fields: List[str] = []
    if drop_non_numeric:
        non_numeric_fields = find_non_numeric_fields(df, available)
        available = [field for field in available if field not in non_numeric_fields]
        if not available:
            raise KeyError("숫자가 아닌 값이 포함된 컬럼만 선택되어 추출할 수 없습니다.")

    output_path = (
        target_path.with_name(filename)
        if filename is not None
        else target_path.with_name(f"{target_path.stem}_extracted.csv")
    )
    df[available].to_csv(output_path, index=False)
    return output_path, missing, non_numeric_fields


def parse_filter_expression(expr: str) -> tuple[str, str, str]:
    operators = ["<=", ">=", "==", "!=", "<", ">", "="]
    for op in operators:
        if op in expr:
            field, value = expr.split(op, 1)
            field, value = field.strip(), value.strip()
            if not field or not value:
                raise ValueError(f"필터 표현식이 올바르지 않습니다: '{expr}'")
            return field, op, value
    raise ValueError(
        "필터 표현식이 올바르지 않습니다. 예: status=OK, voltage>3.6, temp<=25"
    )


def apply_extract_filters(df, filters: List[str]):
    if not filters:
        return df

    mask = pd.Series(True, index=df.index)
    for expr in filters:
        field, op, raw_value = parse_filter_expression(expr)
        if field not in df.columns:
            raise KeyError(f"필터 필드 '{field}'을(를) 찾을 수 없습니다.")

        series = df[field]

        try:
            numeric_value = float(raw_value)
            value_is_numeric = True
        except ValueError:
            value_is_numeric = False
            numeric_value = None

        if op in {">", "<", ">=", "<="}:
            if not value_is_numeric:
                raise ValueError(f"'{op}' 비교는 숫자 값과 함께 사용해야 합니다: {raw_value}")
            comparable = pd.to_numeric(series, errors="coerce")
            if op == ">":
                condition = comparable > numeric_value
            elif op == "<":
                condition = comparable < numeric_value
            elif op == ">=":
                condition = comparable >= numeric_value
            else:
                condition = comparable <= numeric_value
        elif op in {"=", "=="}:
            if value_is_numeric:
                comparable = pd.to_numeric(series, errors="coerce")
                if comparable.notna().any():
                    condition = comparable == numeric_value
                else:
                    condition = series.astype(str) == raw_value
            else:
                condition = series.astype(str) == raw_value
        else:  # op == "!="
            condition = series.astype(str) != raw_value

        mask &= condition.fillna(False)

    return df[mask]


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
    if args.details:
        print_details(field_names, df, args.time_field)
    else:
        print_fields(field_names)

    filtered_df = df
    if args.extract_filter:
        try:
            filtered_df = apply_extract_filters(df, args.extract_filter)
            print(f"필터 적용 후 행 수: {len(filtered_df)} / {len(df)}")
        except Exception as exc:  # noqa: BLE001
            print(f"필터 적용 실패: {exc}")
            return 1

    if args.extract:
        try:
            target = file_paths[0]
            filename = args.extract_output
            if filename is None and len(file_paths) > 1:
                filename = f"{target.stem}_combined_extracted.csv"
            saved_path, missing, non_numeric = extract_fields_to_csv(
                filtered_df,
                args.extract,
                target,
                filename=filename,
                drop_non_numeric=args.drop_non_numeric,
            )
            print(f"추출된 컬럼을 저장했습니다: {saved_path}")
            if missing:
                print(f"다음 컬럼은 존재하지 않아 제외되었습니다: {', '.join(missing)}")
            if non_numeric:
                print(
                    "다음 컬럼은 숫자가 아닌 값이 포함되어 제외되었습니다: "
                    + ", ".join(non_numeric)
                )
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
