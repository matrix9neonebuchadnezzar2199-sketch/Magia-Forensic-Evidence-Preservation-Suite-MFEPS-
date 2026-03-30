"""DvdCssReader — モジュール読込のみ（libdvdcss 未導入環境でも可）"""


def test_dvdcss_reader_module_import():
    from src.core import dvdcss_reader

    assert dvdcss_reader.SECTOR_SIZE == 2048
