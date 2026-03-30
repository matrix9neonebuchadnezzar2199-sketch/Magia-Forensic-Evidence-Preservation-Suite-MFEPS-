"""AacsReader — モジュール読込のみ"""


def test_aacs_reader_module_import():
    from src.core import aacs_reader

    assert aacs_reader.SECTOR_SIZE == 2048
