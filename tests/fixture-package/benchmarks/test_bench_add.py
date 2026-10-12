from pytest_benchmark.fixture import BenchmarkFixture

from fixture_pkg import add


def test_bench_add(benchmark: BenchmarkFixture) -> None:
    assert benchmark(add, 1, 2) == 3
