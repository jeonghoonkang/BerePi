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
from typing import Iterable, List, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CSV 시간/수치 필드 시각화 도구")
    parser.add_argument(
        "csv_path",
        type=Path,
        help="읽을 CSV 파일 경로",
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
        "--list-only",
        action="store_true",
        help="필드명만 출력하고 그래프는 그리지 않습니다",
    )
    return parser.parse_args(argv)


def load_csv(csv_path: Path):
    import pandas as pd

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    return pd.read_csv(csv_path)


def print_fields(df):
    print("\n=== CSV 필드 목록 ===")
    for column in df.columns:
        print(column)
    print("===================\n")


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

    try:
        df = load_csv(args.csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"CSV 로드 실패: {exc}")
        return 1

    print_fields(df)

    if args.list_only:
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
