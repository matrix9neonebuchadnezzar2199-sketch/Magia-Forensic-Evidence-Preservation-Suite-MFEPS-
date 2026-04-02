"""
MFEPS — 監査ログ category 定数（ハードコード回避）
"""


class AuditCategories:
    SYSTEM = "system"
    IMAGING_START = "imaging_start"
    IMAGING_COMPLETE = "imaging_complete"
    IMAGING_CANCEL = "imaging_cancel"
    IMAGING_FAIL = "imaging_fail"
    HASH_MISMATCH = "hash_mismatch"
    HASH_VERIFY = "hash_verify"
    OPTICAL_START = "optical_start"
    OPTICAL_COMPLETE = "optical_complete"
    OPTICAL_CANCEL = "optical_cancel"
    OPTICAL_FAIL = "optical_fail"
    DECRYPT_USED = "decrypt_used"
    E01_START = "e01_start"
    E01_COMPLETE = "e01_complete"
    E01_FAIL = "e01_fail"
