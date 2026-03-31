import asyncio
import os
import sys

# プロジェクトルートにパスを通す
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.database import init_database
from src.core.device_detector import detect_block_devices
from src.services.imaging_service import get_imaging_service
from src.services.case_service import CaseService, EvidenceService
from src.services.coc_service import CoCService
from src.utils.config import get_config

async def main():
    print("=== MFEPS v2.1.0 統合テスト ===")
    
    # DB初期化
    config = get_config()
    init_database(config.db_path)
    
    # 1. デバイス検出
    devices = await asyncio.get_event_loop().run_in_executor(None, detect_block_devices)
    if not devices:
        print("ブロックデバイスが見つかりません!!")
        return
        
    print(f"検出デバイス数: {len(devices)}")
    for d in devices:
        print(f" - {d.device_path} ({d.capacity_bytes / (1024**3):.2f} GB) SYSTEM={d.is_system_drive}")
        
    # テストに安全な非システムドライブを探す
    target_device = next((d for d in devices if not d.is_system_drive), None)
    if not target_device:
        print("安全なテスト用デバイス（非システムドライブ）が見つかりません。テストを中止します。")
        return
        
    print(f"\nターゲットデバイス決定: {target_device.device_path}")
    
    # 2. イメージング開始 (5秒だけ回してキャンセルする)
    test_case = "TEST-CASE-999"
    test_evidence = "TEST-EV-001"
    
    svc = get_imaging_service()
    print(f"\nイメージングジョブ開始: Case={test_case}, Ev={test_evidence}")
    job_id = await svc.start_imaging(
        device=target_device,
        case_id=test_case,
        evidence_id=test_evidence,
        verify=False
    )
    
    print(f"ジョブID = {job_id}")
    
    # 3. 進捗監視 (3秒間)
    for _ in range(3):
        await asyncio.sleep(1)
        prog = svc.get_progress(job_id)
        print(f"進捗: Status={prog.get('status')} | Copied={prog.get('copied_bytes', 0)} / {prog.get('total_bytes', 0)}")
        
    # 4. キャンセル実行
    print("ジョブをキャンセルします...")
    await svc.cancel_imaging(job_id)
    await asyncio.sleep(1) # DB/ファイルのフラッシュ待ち
    
    prog = svc.get_progress(job_id)
    print(f"キャンセル後ステータス: {prog.get('status')}")
    
    # 5. DB確認
    case_svc = CaseService()
    case_id = case_svc.get_or_create_case(test_case)
    ev_svc = EvidenceService()
    ev_id = ev_svc.get_or_create_evidence(case_id, test_evidence)
    
    coc_svc = CoCService()
    entries = coc_svc.get_entries(ev_id)
    
    print(f"\nCoC エントリ確認 (証拠品ID: {test_evidence} -> 内部ID: {ev_id}):")
    for e in entries:
        print(f" [{e['timestamp']}] {e['action']} by {e['actor_name']} -> {e['description']}")

if __name__ == "__main__":
    asyncio.run(main())
