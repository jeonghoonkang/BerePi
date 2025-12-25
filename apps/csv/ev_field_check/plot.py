"""CSV를 시각화하는 보조 스크립트.

기능 요약
- CSV 파일을 로드해 시간 컬럼(x축)과 수치 컬럼(y축)을 그래프로 표시합니다.
- y축 컬럼을 지정하지 않으면 시간 컬럼을 제외한 모든 컬럼을 그립니다.
- --normalize 옵션으로 여러 컬럼을 첫 유효 값 기준으로 정규화할 수 있습니다.
- 인자 파일(@args.txt)로부터 명령행 인자를 읽어 실행할 수 있습니다.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import matplotlib.pyplot as plt
import pandas as pd


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSV 시간/수치 필드 그래프 도구",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        fromfile_prefix_chars="@",
    )
    parser.add_argument("csv_path", type=Path, help="읽을 CSV 파일 경로")
    parser.add_argument(
        "--time-field",
        required=True,
        help="x축에 사용할 시간 컬럼명",
    )
    parser.add_argument(
        "--y-fields",
        nargs="+",
        help="y축에 사용할 컬럼명(여러 개 지정 가능). 지정하지 않으면 시간 컬럼 외 모든 컬럼 사용",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="여러 수치 컬럼을 첫 유효 값으로 나누어 동일 기준으로 정규화",
    )
    parser.add_argument(
        "--drop-non-numeric",
        action="store_true",
        help="수치로 변환할 수 없는 컬럼을 제외하고 그립니다",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    return pd.read_csv(csv_path)


def select_y_fields(df: pd.DataFrame, time_field: str, y_fields: List[str] | None) -> List[str]:
    if y_fields:
        missing = [col for col in y_fields if col not in df.columns]
        if missing:
            raise KeyError(f"존재하지 않는 컬럼: {', '.join(missing)}")
        return y_fields

    return [col for col in df.columns if col != time_field]


def drop_non_numeric_fields(df: pd.DataFrame, y_fields: List[str]) -> tuple[pd.DataFrame, List[str], List[str]]:
    numeric_fields: List[str] = []
    excluded_fields: List[str] = []
    cleaned_df = df.copy()

    for field in y_fields:
        series = cleaned_df[field]
        numeric_series = pd.to_numeric(series, errors="coerce")
        non_numeric_mask = series.notna() & numeric_series.isna()

        if non_numeric_mask.any():
            excluded_fields.append(field)
            cleaned_df = cleaned_df.drop(columns=[field])
        else:
            cleaned_df[field] = numeric_series
            numeric_fields.append(field)

    return cleaned_df, numeric_fields, excluded_fields


def normalize_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    normalized = df.copy()
    for col in columns:
        series = normalized[col]
        first_valid = series.dropna().iloc[0] if not series.dropna().empty else None
        if first_valid is None or first_valid == 0:
            print(f"[경고] 컬럼 '{col}'을(를) 정규화할 수 없습니다 (첫 유효 값 없음 또는 0)")
            continue
        normalized[col] = series / first_valid
    return normalized


def plot_columns(
    df: pd.DataFrame, time_field: str, y_fields: List[str], *, normalized: bool
) -> None:
    if time_field not in df.columns:
        raise KeyError(f"시간 컬럼 '{time_field}'을(를) 찾을 수 없습니다.")

    time_series = pd.to_datetime(df[time_field], errors="coerce")
    if time_series.isna().all():
        raise ValueError(f"시간 컬럼 '{time_field}'에서 유효한 시간을 찾을 수 없습니다.")

    plt.figure(figsize=(10, 6))
    for field in y_fields:
        plt.plot(time_series, df[field], label=field)

    plt.xlabel(time_field)
    ylabel = "정규화된 값" if normalized and len(y_fields) > 1 else "값"
    plt.ylabel(ylabel)
    plt.title("시간에 따른 컬럼 변화")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        df = load_csv(args.csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"CSV 로드 실패: {exc}")
        return 1

    y_fields = select_y_fields(df, args.time_field, args.y_fields)
    if not y_fields:
        print("y축에 사용할 컬럼이 없습니다. --y-fields 로 지정하거나 CSV 내용을 확인하세요.")
        return 1

    plot_df = df
    if args.drop_non_numeric:
        plot_df, y_fields, excluded = drop_non_numeric_fields(plot_df, y_fields)
        if excluded:
            print("다음 컬럼은 비수치 값이 있어 제외되었습니다: " + ", ".join(excluded))
        if not y_fields:
            print("남은 수치 컬럼이 없습니다. CSV 데이터를 확인하세요.")
            return 1

    plot_df = normalize_columns(plot_df, y_fields) if args.normalize else plot_df

    try:
        plot_columns(plot_df, args.time_field, y_fields, normalized=args.normalize)
    except Exception as exc:  # noqa: BLE001
        print(f"그래프 생성 실패: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
