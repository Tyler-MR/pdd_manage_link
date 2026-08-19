"""
B 电脑统一操作任务监听脚本
===========================

一个 worker 串行监听利润看板的统一任务队列，同时支持：
  - task_type=delist：产品下架
  - task_type=promotion_adjust：调整投产

工作方式：
  1. 轮询 /api/operation/queue，按创建顺序放入本地 FIFO 队列；
  2. 同一时间只生成一个任务文件和一个 new_task.txt 触发文件；
  3. 开始前调用 /api/operation/start 标记执行中；收到中断请求时清理任务文件；
  4. B 电脑上的影刀/RPA 根据 trigger 中的 task_type 分流执行；
  5. RPA 完成后删除 new_task.txt，worker 检测到删除后调用
     /api/operation/complete 回写任务结果，再处理下一条。

运行：
  python b_computer_delist_worker.py

依赖：
  pip install requests openpyxl

环境变量：
  LINK_MANAGEMENT_API_BASE：链接群控看板地址，默认 https://link-management.tyler-personnal.top
  PROFIT_API_BASE / DELIST_API_BASE：旧版环境变量名称，继续兼容
  OPERATION_TASK_DIR：任务文件目录，默认 C:\DelistTasks
  OPERATION_POLL_INTERVAL：轮询秒数，默认 10
"""

import csv
import json
import os
import time
import traceback
from datetime import datetime

import requests


DEFAULT_API_BASE = "https://link-management.tyler-personnal.top"
WORKER_VERSION = "2026-08-18.identity-xlsx-v4"
API_BASE = (
    os.getenv("LINK_MANAGEMENT_API_BASE")
    or os.getenv("PROFIT_API_BASE")
    or os.getenv("DELIST_API_BASE")
    or DEFAULT_API_BASE
).rstrip("/")
TASK_DIR = os.getenv("OPERATION_TASK_DIR", r"C:\DelistTasks")
POLL_INTERVAL = max(2, int(os.getenv("OPERATION_POLL_INTERVAL", "10")))

WORKBOOK_FILE = os.path.join(TASK_DIR, "pending_tasks.xlsx")
TRIGGER_FILE = os.path.join(TASK_DIR, "new_task.txt")
COMPLETED_FILE = os.path.join(TASK_DIR, "completed_ids.json")

OPERATION_NAMES = {
    "delist": "产品下架",
    "promotion_adjust": "调整投产",
}
PROMOTION_ADJUST_PRESETS = {
    "maintenance-005": {"label": "日常维护", "display": "+0.05"},
    "serious-loss-01": {"label": "亏损严重", "display": "+0.1"},
    "serious-loss-02": {"label": "亏损严重", "display": "+0.2"},
    "maintenance-001": {"label": "日常维护", "display": "+0.01"},
}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def scheduled_datetime(task):
    """读取任务的计划时间；空值表示立即执行。"""
    raw = str(task.get("scheduled_at") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        # API 已经会拦截非法的新任务；旧任务如果字段损坏，跳过而不是误执行。
        return None


def created_datetime(task):
    """读取任务发起时间，供统一队列稳定执行 FIFO。"""
    raw = str(task.get("created_at") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def schedule_is_due(task):
    planned_at = scheduled_datetime(task)
    if planned_at is None and str(task.get("scheduled_at") or "").strip():
        print(f"[{now_text()}] 跳过无效计划时间任务：{task.get('id', '')}")
        return False
    return planned_at is None or planned_at <= datetime.now()


def load_completed():
    if not os.path.exists(COMPLETED_FILE):
        return set()
    try:
        with open(COMPLETED_FILE, "r", encoding="utf-8") as f:
            value = json.load(f)
        return set(str(item) for item in value)
    except (OSError, TypeError, ValueError):
        return set()


def save_completed(task_ids):
    os.makedirs(TASK_DIR, exist_ok=True)
    with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(task_ids), f, ensure_ascii=False, indent=2)


def fetch_queue_snapshot():
    try:
        response = requests.get(f"{API_BASE}/api/operation/queue", timeout=15)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except requests.exceptions.ConnectionError:
        print(f"[{now_text()}] 无法连接 {API_BASE}")
    except Exception as exc:
        print(f"[{now_text()}] 拉取统一任务队列失败：{exc}")
    return None


def mark_started(task_id):
    try:
        response = requests.post(
            f"{API_BASE}/api/operation/start",
            json={"task_id": task_id},
            timeout=15,
        )
        if not response.ok:
            print(f"[{now_text()}] 标记执行中失败 {task_id}: HTTP {response.status_code} {response.text}")
        return response.ok
    except Exception as exc:
        print(f"[{now_text()}] 标记执行中失败 {task_id}: {exc}")
        return False


def mark_completed(task_id, result="ok", error=""):
    try:
        response = requests.post(
            f"{API_BASE}/api/operation/complete",
            json={"task_id": task_id, "result": result, "error": error},
            timeout=15,
        )
        if not response.ok:
            print(f"[{now_text()}] 回写任务失败 {task_id}: HTTP {response.status_code} {response.text}")
        return response.ok
    except Exception as exc:
        print(f"[{now_text()}] 回写任务失败 {task_id}: {exc}")
        return False


def cleanup_task_files():
    """清理尚未被 RPA 消费的任务文件，用于确认中断或启动失败回滚。"""
    paths = [TRIGGER_FILE, WORKBOOK_FILE, WORKBOOK_FILE.replace(".xlsx", ".csv")]
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            print(f"[{now_text()}] 清理任务文件失败 {path}: {exc}")


def _task_type(task):
    value = str(task.get("task_type") or task.get("operation_type") or task.get("operation") or "delist").strip().lower()
    return value if value in {"delist", "promotion_adjust"} else "delist"


def _safe_list(value):
    return value if isinstance(value, list) else []


def _adjustment_meta(task):
    """读取 API 规范化后的档次字段，并兼容旧任务的 direction/value。"""
    preset_key = str(task.get("adjustment_preset_key") or "").strip().lower()
    preset = PROMOTION_ADJUST_PRESETS.get(preset_key)
    label = str(task.get("adjustment_label") or (preset or {}).get("label") or "自定义调整")
    display = str(task.get("adjustment_display") or (preset or {}).get("display") or "")
    if not display:
        try:
            value = float(task.get("value"))
            number = f"{value:.2f}".rstrip("0").rstrip(".")
            display = f"{'+' if str(task.get('direction', '')).lower() == 'up' else '-'}{number}"
        except (TypeError, ValueError):
            display = str(task.get("value", ""))
    return {
        "preset_key": preset_key,
        "label": label,
        "display": display,
        "value": task.get("value", ""),
    }


def _operation_label(task, task_type):
    if task_type == "delist":
        return str(task.get("operation_label") or "产品下架")
    meta = _adjustment_meta(task)
    return str(task.get("operation_label") or f"{meta['label']} {meta['display']}")


def _task_identity_value(task, *keys):
    """按兼容字段顺序读取身份，保证旧版任务也能写入新 Excel 列。"""
    for key in keys:
        value = str(task.get(key) or "").strip()
        if value:
            return value

    # 兼容部分旧接口把身份放在 identity/user/operator_info 子对象中的情况。
    for container_key in ("identity", "user", "operator_info"):
        container = task.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = str(container.get(key) or "").strip()
            if value:
                return value
    return ""


def write_task_files(task):
    """生成统一 Excel 和触发文件，返回触发文件路径。"""
    task_id = str(task.get("id", "")).strip()
    task_type = _task_type(task)
    link_ids = [str(item).strip() for item in _safe_list(task.get("link_ids"))]
    store_names = [str(item).strip() for item in _safe_list(task.get("store_names"))]
    dingtalk_userid = _task_identity_value(
        task, "operator_id", "dingtalk_userid", "dingtalk_user_id", "dingding_userid", "userid", "userId"
    )
    dingtalk_username = _task_identity_value(
        task, "dingtalk_username", "dingtalk_user_name", "dingding_username", "username", "name"
    )
    operator = str(task.get("operator") or dingtalk_username).strip()
    if (
        not dingtalk_username
        and dingtalk_userid
        and operator
        and operator not in {"链接监控", "数据中台", "系统", "管理员"}
    ):
        # 兼容已经入队的旧任务：旧接口曾把真实姓名只写入 operator。
        dingtalk_username = operator
    created_at = str(task.get("created_at", ""))
    operation_name = OPERATION_NAMES[task_type]
    operation_label = _operation_label(task, task_type)

    # 身份为空时不能静默处理，否则 Excel 虽然有列名但会产生无法追溯的空值。
    # 打印原始相关字段名，便于确认是中台没有注入，还是 B 电脑运行了旧脚本。
    if not dingtalk_userid or not dingtalk_username:
        identity_keys = sorted(
            key for key in task.keys()
            if any(token in str(key).lower() for token in ("ding", "user", "operator"))
        )
        print(
            f"[{now_text()}] 身份字段为空：task_id={task_id or '<empty>'}，"
            f"operator={operator!r}，dingtalk_userid={dingtalk_userid!r}，"
            f"dingtalk_username={dingtalk_username!r}，相关字段={identity_keys}"
        )

    if not task_id or not link_ids:
        print(f"[{now_text()}] 跳过无效任务：{task_id or '<empty>'}")
        return None

    os.makedirs(TASK_DIR, exist_ok=True)
    if task_type == "promotion_adjust":
        adjustment = _adjustment_meta(task)
        direction = str(task.get("direction", "")).lower()
        direction_label = "上调" if direction == "up" else "下调"
        headers = ["任务ID", "任务类型", "链接ID", "店铺名称", "操作人", "钉钉userid", "钉钉用户名", "创建时间", "调整方向", "调整数值", "状态", "操作名称", "投产档次", "调整显示"]
        rows = []
        for index, link_id in enumerate(link_ids):
            store_name = store_names[index] if index < len(store_names) else ""
            rows.append([
                task_id, task_type, link_id, store_name, operator, dingtalk_userid, dingtalk_username, created_at,
                direction_label, task.get("value", ""), "待处理", operation_name,
                adjustment["label"], adjustment["display"],
            ])
        flow_name = "店大人批量调整投产"
    else:
        headers = ["任务ID", "任务类型", "链接ID", "店铺名称", "操作人", "钉钉userid", "钉钉用户名", "创建时间", "状态", "操作名称"]
        rows = []
        for index, link_id in enumerate(link_ids):
            store_name = store_names[index] if index < len(store_names) else ""
            rows.append([task_id, task_type, link_id, store_name, operator, dingtalk_userid, dingtalk_username, created_at, "待处理", operation_name])
        flow_name = "店大人批量下架操作"

    # 保留原有中文列，同时追加稳定的英文键名，方便影刀/RPA按字段名读取。
    headers.extend(["dingtalk_userid", "dingtalk_username"])
    rows = [row + [dingtalk_userid, dingtalk_username] for row in rows]

    try:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "操作任务"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        column_widths = [18, 22, 18, 30, 14, 24, 20, 22, 14, 14, 10, 16, 16, 16, 24, 20]
        for index, width in enumerate(column_widths[:len(headers)], 1):
            sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
        workbook.save(WORKBOOK_FILE)
    except ImportError:
        csv_file = WORKBOOK_FILE.replace(".xlsx", ".csv")
        with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    except Exception:
        print(f"[{now_text()}] 写入任务文件失败：{task_id}")
        traceback.print_exc()
        return None

    unique_stores = sorted({name for name in store_names if name})
    trigger_lines = [
        f"task_id={task_id}",
        f"task_type={task_type}",
        f"operation={task_type}",
        f"operation_type={task_type}",
        f"operation_name={operation_name}",
        f"operation_label={operation_label}",
        f"dingtalk_userid={dingtalk_userid}",
        f"dingtalk_username={dingtalk_username}",
        "platform=拼多多",
        f"flow_name={flow_name}",
        f"link_count={len(link_ids)}",
        f"unique_stores={','.join(unique_stores)}",
        f"excel_path={WORKBOOK_FILE}",
        f"triggered_at={now_text()}",
    ]
    if task_type == "promotion_adjust":
        adjustment = _adjustment_meta(task)
        trigger_lines.extend([
            f"direction={task.get('direction', '')}",
            f"adjustment_preset_key={adjustment['preset_key']}",
            f"adjustment_label={adjustment['label']}",
            f"adjustment_display={adjustment['display']}",
            f"adjustment_value={task.get('value', '')}",
        ])

    try:
        with open(TRIGGER_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(trigger_lines))
    except OSError:
        print(f"[{now_text()}] 写入触发文件失败：{TRIGGER_FILE}")
        traceback.print_exc()
        return None

    print(f"[{now_text()}] 已触发 {operation_label}: {task_id}，{len(link_ids)} 条链接")
    return TRIGGER_FILE


def main():
    print(f"  worker version: {WORKER_VERSION}")
    print("=" * 64)
    print("  B 电脑统一操作任务监听服务")
    print("  支持：产品下架 + 调整投产 | 单队列 FIFO | 同时只执行 1 个任务")
    print("=" * 64)
    print(f"  API 地址：{API_BASE}")
    print(f"  任务目录：{TASK_DIR}")
    print(f"  轮询间隔：{POLL_INTERVAL}s")
    print("=" * 64)

    completed = load_completed()
    pending_queue = []
    active_task_id = None

    while True:
        try:
            snapshot = fetch_queue_snapshot()
            remote_tasks = snapshot.get("tasks", []) if snapshot else []
            remote_status = {
                str(task.get("id", "")).strip(): str(task.get("status") or "pending").lower()
                for task in remote_tasks
                if str(task.get("id", "")).strip()
            }

            # 执行中任务收到中断请求后，优先清理触发文件并回写取消结果。
            if active_task_id and remote_status.get(active_task_id) == "cancelling":
                cleanup_task_files()
                if mark_completed(active_task_id, result="cancelled"):
                    print(f"[{now_text()}] 任务已中断：{active_task_id}")
                    completed.add(active_task_id)
                    save_completed(completed)
                    active_task_id = None

            # 触发文件被影刀/RPA 删除，代表当前任务已执行完成。
            if active_task_id and not os.path.exists(TRIGGER_FILE):
                if mark_completed(active_task_id):
                    print(f"[{now_text()}] 任务完成：{active_task_id}")
                    completed.add(active_task_id)
                    save_completed(completed)
                    active_task_id = None
                else:
                    print(f"[{now_text()}] 任务结果暂未回写，保留当前任务等待重试：{active_task_id}")

            # 用服务端实时 pending 列表同步本地等待队列，已取消任务立即移除。
            if snapshot is not None:
                remote_pending_ids = {
                    str(task.get("id", "")).strip()
                    for task in remote_tasks
                    if str(task.get("status") or "pending").lower() == "pending"
                }
                pending_queue = [item for item in pending_queue if item[0] in remote_pending_ids]

            # 服务端的 created_at 是“发起时间”；每轮都按它排序，避免 API 文件中
            # 混入旧任务或两个来源文件后，B 电脑按返回顺序误执行。
            ordered_tasks = sorted(
                remote_tasks,
                key=lambda task: (
                    created_datetime(task) is None,
                    created_datetime(task) or datetime.max,
                ),
            )
            # 统一队列中的两种任务按发起时间进入同一个 FIFO 队列。
            for task in ordered_tasks:
                if str(task.get("status") or "pending").lower() != "pending":
                    continue
                if not schedule_is_due(task):
                    continue
                task_id = str(task.get("id", "")).strip()
                if not task_id or task_id in completed or task_id == active_task_id:
                    continue
                if any(item[0] == task_id for item in pending_queue):
                    continue
                pending_queue.append((task_id, task))
                print(f"[{now_text()}] 加入队列：{task_id} ({_task_type(task)})，发起于 {task.get('created_at') or '—'}，排队 {len(pending_queue)}")

            pending_queue.sort(
                key=lambda item: (
                    created_datetime(item[1]) is None,
                    created_datetime(item[1]) or datetime.max,
                )
            )

            # 只允许一个任务占用固定的 Excel 和触发文件。
            if not active_task_id and pending_queue:
                task_id, task = pending_queue.pop(0)
                if os.path.exists(TRIGGER_FILE):
                    print(f"[{now_text()}] 触发文件仍存在，暂不覆盖：{TRIGGER_FILE}")
                    pending_queue.insert(0, (task_id, task))
                else:
                    if not mark_started(task_id):
                        print(f"[{now_text()}] 任务可能已被取消，跳过启动：{task_id}")
                    elif write_task_files(task):
                        active_task_id = task_id
                    else:
                        mark_completed(task_id, result="failed", error="生成任务文件失败")

            if active_task_id:
                print(f"[{now_text()}] 执行中：{active_task_id} | 等待：{len(pending_queue)}")
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{now_text()}] 用户中断监听")
            break
        except Exception as exc:
            print(f"[{now_text()}] 监听异常：{exc}")
            traceback.print_exc()
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
