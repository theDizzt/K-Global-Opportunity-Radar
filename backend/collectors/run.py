# 0. 모듈 불러오기
import argparse

from backend.collectors.mofa import DATASETS, MofaCollector


# 1. 명령행에서 외교부 LOD 수집 실행
def main():
    parser = argparse.ArgumentParser(description="외교부 LOD 데이터를 수집합니다.")
    parser.add_argument(
        "--datasets",
        default="mofadaily,mofapress",
        help="쉼표로 구분한 데이터셋 코드",
    )
    parser.add_argument("--countries", default="", help="쉼표로 구분한 ISO3 국가 코드")
    parser.add_argument("--limit", type=int, default=None, help="데이터셋별 최대 조회 건수")
    args = parser.parse_args()

    datasets = tuple(value.strip() for value in args.datasets.split(",") if value.strip())
    countries = [value.strip() for value in args.countries.split(",") if value.strip()] or None
    unknown = set(datasets) - set(DATASETS)
    if unknown:
        parser.error(f"지원하지 않는 데이터셋: {', '.join(sorted(unknown))}")

    with MofaCollector() as collector:
        result = collector.collect(countries, datasets, args.limit)
    print(
        f"외교부 LOD 수집 완료: 국가 {result.countries}개, "
        f"문서 {result.documents}건, 데이터셋 {', '.join(result.datasets)}"
    )


# 2. 파일을 직접 실행했을 때 수집 시작
if __name__ == "__main__":
    main()
