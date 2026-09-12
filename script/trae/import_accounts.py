#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae CN 账号导入工具与设备 ID 解析

将本机已有的 Trae CN 账号批量导入到 config/token.json 的 trae 节点。

支持的导入来源：
1. 官方 Trae CN / Trae 客户端（自动探测，读取 User/globalStorage/storage.json 中
   iCubeAuthInfo://icube.cloudide 的 accessToken，仅导入 AIRegion=CN 账号）
2. cockpit-tools 数据目录（批量导入其 trae_accounts 目录，AES-256-GCM 自动解密）

签到接口只存在于 Trae CN（api.trae.cn），故本工具只保留 CN 账号；
账号按 user_id 去重，同一账号保留令牌有效期（expires_at）最新的来源。

使用示例：
    python import_accounts.py                      # 官方客户端 + cockpit-tools 自动探测导入
    python import_accounts.py --list               # 仅预览，不写入配置
    python import_accounts.py --path D:/xxx.json   # 从指定文件/目录导入
"""

import argparse
import base64
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = project_root / "config" / "token.json"

# cockpit-tools 的 Trae 账号目录与密钥文件名
ACCOUNTS_DIR_NAME = "trae_accounts"
ACCOUNTS_INDEX_FILE = "trae_accounts.json"
KEY_FILE_NAME = "secure-account-storage.key"

# 官方 Trae 客户端 storage.json 的登录态与设备键
AUTH_STORAGE_KEY = "iCubeAuthInfo://icube.cloudide"
DEVICE_STORAGE_KEY_PREFIX = "iCubeAuthInfo://icube-dc:"

# 本机签到设备 ID 持久化文件名（与账号配置同目录，无需入库）
DEVICE_ID_FILE = "trae_device_id.txt"

# 各平台客户端的 %APPDATA% 目录名（CN 客户端优先，设备 ID 解析顺序与此一致）
CN_APP_DIRS = ["TRAE SOLO CN", "Trae CN"]
APP_DIRS = CN_APP_DIRS + ["TRAE SOLO", "Trae"]

try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# HAS_CRYPTO 为 False 时只提示一次，避免逐文件刷屏
_crypto_warned = False

# ============ 客户端登录态解密（AES 信封） ============
# 部分客户端版本（如 TRAE SOLO CN）把 iCubeAuthInfo://icube.cloudide 存为 AES 信封而非明文
# JSON。信封 = HEADER(6) + randomKey(32) + AES-128-CBC( SHA512(payload) ‖ payload )，
# key/iv = SHA512( SHA512(randomKey) ‖ (LEFT_SECRET⊕RIGHT_SECRET) ) 前 32 字节（对齐 trae-mate）。

_ENVELOPE_HEADER = bytes([116, 99, 5, 16, 0, 0])
_LEFT_SECRET = bytes([
    82, 9, 106, 213, 48, 54, 165, 56, 191, 64, 163, 158, 129, 243, 215, 251, 124, 227, 57, 130,
    155, 47, 255, 135, 52, 142, 67, 68, 196, 222, 233, 203, 84, 123, 148, 50, 166, 194, 35, 61,
    238, 76, 149, 11, 66, 250, 195, 78, 8, 46, 161, 102, 40, 217, 36, 178, 118, 91, 162, 73, 109,
    139, 209, 37,
])
_RIGHT_SECRET = bytes([
    31, 221, 168, 51, 136, 7, 199, 49, 177, 18, 16, 89, 39, 128, 236, 95, 96, 81, 127, 169, 25,
    181, 74, 13, 45, 229, 122, 159, 147, 201, 156, 239, 160, 224, 59, 77, 174, 42, 245, 176, 200,
    235, 187, 60, 131, 83, 153, 97, 23, 43, 4, 126, 186, 119, 214, 38, 225, 105, 20, 99, 85, 33,
    12, 125,
])


def _sha512(data: bytes) -> bytes:
    import hashlib
    return hashlib.sha512(data).digest()


def _unpad_pkcs7(data: bytes) -> Optional[bytes]:
    if not data:
        return None
    pad = data[-1]
    if pad == 0 or pad > 16 or data[-pad:] != bytes([pad]) * pad:
        return None
    return data[:-pad]


def decrypt_trae_auth_envelope(encoded: str) -> Optional[Dict[str, Any]]:
    """解密客户端 AES 信封格式的登录态，返回 payload JSON；失败返回 None"""
    if not HAS_CRYPTO:
        return None
    try:
        envelope = base64.b64decode(encoded)
        if len(envelope) <= 38 or envelope[0:6] != _ENVELOPE_HEADER:
            return None
        random_key = envelope[6:38]
        secret = bytes(a ^ b for a, b in zip(_LEFT_SECRET, _RIGHT_SECRET))
        derived = _sha512(_sha512(random_key) + secret)
        cipher = AES.new(derived[0:16], AES.MODE_CBC, iv=derived[16:32])
        plaintext = _unpad_pkcs7(cipher.decrypt(envelope[38:]))
        if plaintext is None or len(plaintext) < 64:
            return None
        payload = plaintext[64:]
        if _sha512(payload) != plaintext[:64]:
            return None
        parsed = json.loads(payload.decode('utf-8'))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def parse_storage_auth_value(raw_value: str) -> Optional[Dict[str, Any]]:
    """解析客户端登录态值：明文 JSON 优先，其次 AES 信封（兼容不同客户端版本）"""
    if raw_value.lstrip().startswith('{'):
        try:
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return decrypt_trae_auth_envelope(raw_value)


def _warn_no_crypto() -> None:
    """遇到加密账号但缺少 pycryptodome 时给出一次性安装提示"""
    global _crypto_warned
    if not _crypto_warned:
        _crypto_warned = True
        print("⚠️  检测到加密存储的账号，但缺少 pycryptodome，无法解密（pip install pycryptodome）")


# ============ 官方客户端读取 ============


def _appdata_roots() -> List[Path]:
    """返回 %APPDATA% 目录（官方客户端默认安装数据目录所在）"""
    roots: List[Path] = []
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA')
        if appdata:
            roots.append(Path(appdata))
        # 环境变量缺失时（如计划任务/无登录 Shell）回退到家目录默认位置
        fallback = Path.home() / 'AppData' / 'Roaming'
        if fallback not in roots:
            roots.append(fallback)
    elif sys.platform == 'darwin':
        roots.append(Path.home() / 'Library' / 'Application Support')
    else:
        xdg = os.environ.get('XDG_CONFIG_HOME')
        if xdg:
            roots.append(Path(xdg))
        roots.append(Path.home() / '.config')
    return roots


def find_local_client_storage_paths() -> List[Tuple[str, Path]]:
    """
    定位官方 Trae 客户端 storage.json（含按账号隔离的独立实例目录）

    独立实例目录命名：`<客户端目录名>_<标识>`（官方客户端多开登录生成），
    例如 `Trae CN_3850969196273683`。这些目录各自登录一个账号并注册了独立设备，
    需要纳入探测以便自动同步令牌与设备配对。

    Returns:
        List[Tuple[str, Path]]: (目录名, storage.json 路径) 列表，不存在返回空
    """
    results: List[Tuple[str, Path]] = []
    for root in _appdata_roots():
        for dir_name in APP_DIRS:
            storage = root / dir_name / 'User' / 'globalStorage' / 'storage.json'
            if storage.is_file():
                results.append((dir_name, storage))
        # 独立实例目录（Trae CN_xxx / TRAE SOLO CN_xxx / Trae_xxx 等）
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            name = child.name
            matched = any(name == base or name.startswith(base + '_') for base in APP_DIRS)
            if not matched:
                continue
            storage = child / 'User' / 'globalStorage' / 'storage.json'
            if storage.is_file():
                results.append((name, storage))
    # 去重（同一 storage 路径可能因大小写/重复根目录出现两次）
    seen: List[Path] = []
    deduped: List[Tuple[str, Path]] = []
    for dir_name, storage in results:
        if storage in seen:
            continue
        seen.append(storage)
        deduped.append((dir_name, storage))
    return deduped


def _read_storage_key_value(storage_path: Path, key: str) -> Optional[Dict[str, Any]]:
    """读取 storage.json 中指定键的登录态（兼容明文 JSON 与 AES 信封两种格式）"""
    try:
        with open(storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    raw = data.get(key)
    if not isinstance(raw, str):
        return None
    return parse_storage_auth_value(raw)


def _read_storage_device_id(storage_path: Path) -> str:
    """
    读取官方客户端 storage.json 中注册的 ICDRS 数字设备 ID

    键名为 `iCubeAuthInfo://icube-dc:<16位数字>`（该键值是与设备 ID 配套的签名密钥，
    不参与解析）。注意：同一客户端目录的设备为该目录"最近注册账号"所用，多账号共用
    同一客户端时会指向同一设备（签到会撞车）。
    """
    try:
        content = storage_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    marker = f'"{DEVICE_STORAGE_KEY_PREFIX}'
    start = content.find(marker)
    if start < 0:
        return ''
    digits = re.match(r'\d+', content[start + len(marker):])
    return digits.group(0) if digits else ''


def scan_client_device_pairs() -> Dict[str, str]:
    """
    扫描官方 Trae 客户端，建立 userId → 本机注册设备 ID 的对应关系

    仅当同一份 storage.json 同时存在登录态（auth，含 userId）与 icube-dc 设备时才能
    确定归属。多账号共用同一客户端（机器级设备）时不区分实例，故「实例目录与主目录
    共用同一设备」的配对会被跳过——那属于共享设备，无法作为某账号的独立身份。
    被 cockpit-tools 注销/切号后的客户端目录无法归属，不会出现在结果中。

    Returns:
        Dict[str, str]: user_id → device_id（仅独立的账号级设备）
    """
    pairs: Dict[str, str] = {}

    def _region_ok(auth: Dict[str, Any]) -> bool:
        region = str(auth.get('AIRegion') or auth.get('userRegion') or '').upper()
        if not region:
            host = str(auth.get('host') or '')
            region = 'CN' if 'api.trae.cn' in host else ('SG' if 'api.trae.ai' in host else '')
        return region == 'CN'

    # 主目录（无 _ 后缀）上的机器级共享设备集合
    machine_devices: set = set()
    for _, storage_path in find_local_client_storage_paths():
        auth = _read_storage_key_value(storage_path, AUTH_STORAGE_KEY)
        if not auth or not _region_ok(auth):
            continue
        device_id = _read_storage_device_id(storage_path)
        if device_id:
            machine_devices.add(device_id)

    for dir_name, storage_path in find_local_client_storage_paths():
        auth = _read_storage_key_value(storage_path, AUTH_STORAGE_KEY)
        if not auth or not auth.get('userId') or not _region_ok(auth):
            continue
        device_id = _read_storage_device_id(storage_path)
        if not device_id:
            continue
        # 实例目录若与主目录共用同一机器级设备 → 跳过（非独立身份）
        if '_' in dir_name and device_id in machine_devices:
            continue
        pairs[str(auth['userId'])] = device_id
    return pairs


def _parse_expires_at(value: Any) -> Optional[int]:
    """将 auth 对象中的过期时间规范化为秒级时间戳（兼容秒/毫秒）"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        ts = int(value)
    elif isinstance(value, str) and value.strip().lstrip('-').isdigit():
        ts = int(value.strip())
    else:
        return None
    if ts > 10_000_000_000:  # 毫秒时间戳
        ts //= 1000
    return ts


def load_accounts_from_local_clients() -> List[Dict[str, Any]]:
    """
    从官方 Trae 客户端读取当前登录的 CN 账号

    Returns:
        List[Dict[str, Any]]: 原始账号数据列表
    """
    accounts: List[Dict[str, Any]] = []
    for dir_name, storage_path in find_local_client_storage_paths():
        auth = _read_storage_key_value(storage_path, AUTH_STORAGE_KEY)
        if not auth:
            continue
        # 区域判定：明文版在 AIRegion，信封版在 host 中体现（api.trae.cn => CN）
        region = str(auth.get('AIRegion') or auth.get('userRegion') or '').upper()
        if not region:
            host = str(auth.get('host') or '')
            region = 'CN' if 'api.trae.cn' in host else ('SG' if 'api.trae.ai' in host else '')
        if region != 'CN':
            continue
        access_token = auth.get('accessToken') or auth.get('token')
        if not access_token:
            continue

        account_obj = auth.get('account')
        username = ''
        if isinstance(account_obj, dict):
            username = account_obj.get('username') or ''

        # 同一目录内同时存在登录态与 icube-dc 设备时，设备归属该登录账号
        device_id = _read_storage_device_id(storage_path)

        accounts.append({
            'user_id': str(auth.get('userId') or ''),
            'nickname': username,
            'email': auth.get('email') or 'unknown',
            'access_token': access_token,
            'expires_at': _parse_expires_at(auth.get('expiresAt')),
            'region': 'CN',
            'source': f'local:{dir_name}',
            'device_id': device_id,
        })
    return accounts


# ============ cockpit-tools 数据目录读取 ============


def find_cockpit_data_dirs() -> List[Path]:
    """
    自动探测本机可能存在的 cockpit-tools 数据目录

    Returns:
        List[Path]: 包含 Trae 账号数据的候选目录列表
    """
    candidates: List[Path] = []
    home = Path.home()

    roots: List[Path] = []
    if sys.platform == 'win32':
        for env_key in ('APPDATA', 'LOCALAPPDATA'):
            value = os.environ.get(env_key)
            if value:
                roots.append(Path(value))
        roots.append(home)
        roots.append(home / '.config')
        roots.append(home / '.local' / 'share')
    elif sys.platform == 'darwin':
        roots.append(home / 'Library' / 'Application Support')
        roots.append(home)
    else:
        roots.append(home / '.config')
        roots.append(home / '.local' / 'share')
        roots.append(home)

    for root in roots:
        if not root.is_dir():
            continue
        try:
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                name = child.name.lower()
                if 'cockpit' in name or 'agtools' in name or 'antigravity' in name:
                    if (child / ACCOUNTS_DIR_NAME).is_dir() or (child / ACCOUNTS_INDEX_FILE).exists():
                        candidates.append(child)
        except PermissionError:
            continue

    return candidates


def find_secure_key(source_dir: Path) -> Optional[Path]:
    """为给定账号来源目录查找解密用的本地密钥文件（同 workbuddy 模块策略）"""
    search_bases: List[Path] = [source_dir]
    if source_dir.name == ACCOUNTS_DIR_NAME:
        search_bases.append(source_dir.parent)
    else:
        search_bases.append(source_dir / ACCOUNTS_DIR_NAME)
    search_bases.append(source_dir.parent)

    for base in search_bases:
        candidate = base / KEY_FILE_NAME
        if candidate.is_file():
            return candidate

    home = Path.home()
    for fallback in (
        home / '.antigravity_cockpit' / KEY_FILE_NAME,
        home / '.config' / 'cockpit-tools' / KEY_FILE_NAME,
        home / '.local' / 'share' / 'cockpit-tools' / KEY_FILE_NAME,
    ):
        if fallback.is_file():
            return fallback

    return None


def decrypt_record(enc: Dict[str, Any], key: bytes) -> Optional[Dict[str, Any]]:
    """使用本地密钥解密 AES-256-GCM 加密的账号记录"""
    if not HAS_CRYPTO:
        _warn_no_crypto()
        return None
    try:
        nonce = base64.b64decode(enc['nonce'])
        ct = base64.b64decode(enc['ciphertext'])
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plain = cipher.decrypt_and_verify(ct[:-16], ct[-16:])
        return json.loads(plain.decode('utf-8'))
    except Exception as e:
        print(f"⚠️  解密失败: {e}")
        return None


def load_accounts_from_cockpit_dir(directory: Path, quiet: bool = False) -> List[Dict[str, Any]]:
    """
    从 cockpit-tools 数据目录读取 Trae 账号（兼容明文与 AES-256-GCM 加密）

    Args:
        directory (Path): cockpit-tools 数据目录（含 trae_accounts 子目录）
        quiet (bool): True 时不输出警告信息

    Returns:
        List[Dict[str, Any]]: 原始账号数据列表
    """
    accounts_dir = directory / ACCOUNTS_DIR_NAME
    if not accounts_dir.is_dir():
        return []

    key_path = find_secure_key(directory)
    key = None
    if key_path:
        try:
            key = base64.b64decode(key_path.read_text(encoding='utf-8').strip())
        except Exception as e:
            if not quiet:
                print(f"⚠️  读取密钥失败: {e}")

    accounts: List[Dict[str, Any]] = []
    for json_file in sorted(accounts_dir.glob('*.json')):
        if json_file.name == ACCOUNTS_INDEX_FILE or json_file.name.endswith('.bak'):
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if not quiet:
                print(f"⚠️  跳过无法解析的文件 {json_file.name}: {e}")
            continue

        if isinstance(data, dict) and data.get('ciphertext'):
            if not key:
                if not quiet:
                    print(f"⚠️  跳过加密账号 {json_file.name}: 未找到解密密钥 {KEY_FILE_NAME}")
                continue
            data = decrypt_record(data, key)
            if not data:
                continue

        if not isinstance(data, dict) or not data.get('access_token'):
            continue

        # 仅保留 CN 账号（cockpit 混存多平台 Trae 账号时过滤掉国际版）
        auth_raw = data.get('trae_auth_raw')
        region = ''
        if isinstance(auth_raw, dict):
            region = str(auth_raw.get('AIRegion') or '')
        if region and region.upper() != 'CN':
            continue

        account_id = data.get('id') or ''
        user_id = data.get('user_id')
        if user_id is None:
            # cockpit 账号结构里 user_id 可能是 int；没有则用账号 id 兜底去重
            user_id = account_id
        user_id = str(user_id)

        accounts.append({
            'account_id': account_id,
            'user_id': user_id,
            'nickname': data.get('nickname') or '',
            'email': data.get('email') or 'unknown',
            'access_token': data['access_token'],
            'expires_at': data.get('expires_at'),
            'region': 'CN',
            'source': f'cockpit:{directory.name}',
        })
    return accounts


# ============ 账号合并 ============


def account_identity(account: Dict[str, Any]) -> str:
    """账号唯一标识（user_id），用于导入去重"""
    return (account.get('user_id') or account.get('email') or account.get('nickname') or '').strip().lower()


def _merge_best_expires(account: Dict[str, Any], best_expires: Dict[str, int]) -> bool:
    """判断候选账号是否为同身份中令牌最新者，是则记录并返回 True"""
    identity = account_identity(account)
    expires = account.get('expires_at')
    if expires is None:
        # 无法比较时保留既有最佳候选，仅当尚无候选时采纳
        if identity not in best_expires:
            best_expires[identity] = -1
            return True
        return False
    prev = best_expires.get(identity, -1)
    if expires >= prev:
        best_expires[identity] = expires
        return True
    return False


def convert_account(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    将来源账号结构转换为本项目配置结构

    Args:
        raw (Dict[str, Any]): 来自 cockpit-tools / 官方客户端的原始账号

    Returns:
        Optional[Dict[str, Any]]: 转换后的账号配置，缺少令牌时返回 None
    """
    access_token = raw.get('access_token')
    if not access_token:
        return None

    account_name = raw.get('nickname') or raw.get('email') or raw.get('account_id') or '未命名账号'

    # 只保留签到必需字段；region 过滤缺省即 CN，无需落盘
    account: Dict[str, Any] = {
        'account_name': account_name,
        'user_id': raw.get('user_id', ''),
        'access_token': access_token,
    }
    for key in ('expires_at', 'device_id'):
        value = raw.get(key)
        if value:
            account[key] = value
    return account


def merge_into_config(new_accounts: List[Dict[str, Any]], config_path: Path) -> Dict[str, int]:
    """
    将账号合并写入配置文件的 trae 节点

    同一 user_id 的账号更新令牌（保留自定义 account_name），新账号追加写入。

    Args:
        new_accounts (List[Dict[str, Any]]): 待导入的账号（已转换、已去重）
        config_path (Path): 配置文件路径

    Returns:
        Dict[str, int]: 包含 added 和 updated 数量的统计字典
    """
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}

    trae_node = config_data.setdefault('trae', {})
    existing: List[Dict[str, Any]] = trae_node.setdefault('accounts', [])

    index_map = {}
    for idx, acc in enumerate(existing):
        identity = account_identity(acc)
        if identity:
            index_map[identity] = idx

    added = 0
    updated = 0
    for account in new_accounts:
        identity = account_identity(account)
        if identity and identity in index_map:
            target = existing[index_map[identity]]
            for key, value in account.items():
                if key == 'account_name':
                    continue
                if key == 'source':
                    continue
                target[key] = value
            updated += 1
        else:
            existing.append(account)
            if identity:
                index_map[identity] = len(existing) - 1
            added += 1

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    return {'added': added, 'updated': updated}


def collect_accounts(quiet: bool = False) -> List[Dict[str, Any]]:
    """
    自动探测本机账号来源并采集 CN 账号（已按 user_id 去重、取令牌最新者）

    来源顺序：cockpit-tools 数据目录 → 官方 Trae 客户端。
    官方客户端放在最后处理：其令牌来自用户最近一次登录会话，同 user_id 时优先。

    Args:
        quiet (bool): True 时不输出来源提示

    Returns:
        List[Dict[str, Any]]: 转换后的账号配置列表，无可用来源时返回空列表
    """
    log = (lambda *a, **k: None) if quiet else print
    raw_accounts: List[Dict[str, Any]] = []

    for candidate in find_cockpit_data_dirs():
        found = load_accounts_from_cockpit_dir(candidate, quiet=quiet)
        if found:
            log(f"📂 来源: {candidate} (发现 {len(found)} 个 CN 账号)")
            raw_accounts.extend(found)

    local = load_accounts_from_local_clients()
    if local:
        log(f"📂 来源: 官方 Trae 客户端 (发现 {len(local)} 个 CN 账号)")
        raw_accounts.extend(local)

    # 同身份账号保留令牌有效期最新者，其次保留来源靠后者
    accounts: List[Dict[str, Any]] = []
    best_expires: Dict[str, int] = {}
    seen: Dict[str, int] = {}
    for raw in raw_accounts:
        converted = convert_account(raw)
        if not converted:
            continue
        identity = account_identity(converted)
        if identity:
            if identity in seen:
                if not _merge_best_expires(converted, best_expires):
                    continue
                accounts[seen[identity]] = converted
                continue
            seen[identity] = len(accounts)
            _merge_best_expires(converted, best_expires)
        accounts.append(converted)

    # 账号级设备 ID 补齐：官方客户端同一目录同时有登录态 + icube-dc 设备时才可归属，
    # 归属成功写入 account.device_id（签到请求必须携带账号自己注册的设备）。
    device_pairs = scan_client_device_pairs()
    if device_pairs:
        matched = 0
        for account in accounts:
            user_id = str(account.get('user_id') or '')
            if not account.get('device_id') and user_id in device_pairs:
                account['device_id'] = device_pairs[user_id]
                matched += 1
        if matched:
            log(f"📱 已按官方客户端目录配对 {matched} 个账号的签到设备 ID")

    return accounts


def sync_accounts(config_path: Optional[Path] = None, quiet: bool = False) -> Optional[Dict[str, int]]:
    """
    从本机 cockpit-tools / 官方客户端同步账号到配置文件（签到前的自动刷新入口）

    Args:
        config_path (Optional[Path]): 配置文件路径，默认项目根目录 config/token.json
        quiet (bool): True 时不输出任何提示信息

    Returns:
        Optional[Dict[str, int]]: 同步统计 {'added': n, 'updated': n}；
                                  未找到来源或无 CN 账号时返回 None
    """
    log = (lambda *a, **k: None) if quiet else print
    try:
        accounts = collect_accounts(quiet=quiet)
        if not accounts:
            return None
        stats = merge_into_config(accounts, config_path or CONFIG_PATH)
        log(f"✅ 同步完成: 新增 {stats['added']} 个，更新 {stats['updated']} 个")
        return stats
    except Exception as e:
        log(f"⚠️  同步失败（不影响签到）: {e}")
        return None


# ============ 签到设备 ID ============


def extract_local_icdrs_device_id() -> Optional[str]:
    """
    从本机 Trae CN 客户端 storage.json 提取 ICDRS 数字设备 ID

    签到接口的 x-device-id 必须与客户端设备注册时一致（键名 iCubeAuthInfo://icube-dc:<did>），
    否则服务端返回 9074 "当前参与用户太多" 拒绝领取。逻辑对齐 cockpit-tools。

    Returns:
        Optional[str]: ICDRS 设备 ID，未找到返回 None
    """
    for dir_name in CN_APP_DIRS:
        for root in _appdata_roots():
            storage_path = root / dir_name / 'User' / 'globalStorage' / 'storage.json'
            if not storage_path.is_file():
                continue
            try:
                content = storage_path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            marker = f'"{DEVICE_STORAGE_KEY_PREFIX}'
            start = content.find(marker)
            if start < 0:
                continue
            digits = re.match(r'\d+', content[start + len(marker):])
            if digits:
                return digits.group(0)
    return None


def get_or_create_device_id(config_dir: Optional[Path] = None) -> str:
    """
    获取签到用设备 ID：优先本机 Trae 客户端注册的 ICDRS 设备 ID，
    其次读取已持久化 ID，都没有时生成一次并持久化。

    Args:
        config_dir (Optional[Path]): 设备 ID 文件所在目录，默认项目 config 目录

    Returns:
        str: 设备 ID
    """
    base_dir = Path(config_dir) if config_dir else project_root / "config"
    path = base_dir / DEVICE_ID_FILE

    icdrs_id = extract_local_icdrs_device_id()
    if icdrs_id:
        try:
            persisted = path.read_text(encoding='utf-8').strip()
        except OSError:
            persisted = ''
        if persisted != icdrs_id:
            try:
                base_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(icdrs_id, encoding='utf-8')
                print(f"📱 已采用本机 Trae 客户端 ICDRS 设备 ID: {icdrs_id}")
            except OSError:
                pass
        return icdrs_id

    try:
        persisted = path.read_text(encoding='utf-8').strip()
        if persisted:
            return persisted
    except OSError:
        pass

    device_id = f"{int(time.time() * 1000)}_{random.randint(0, 2**32 - 1)}"
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(device_id, encoding='utf-8')
    except OSError:
        pass
    return device_id


def read_device_id(config_dir: Optional[Path] = None) -> str:
    """仅读取已持久化的设备 ID（不主动生成），无则返回空串"""
    base_dir = Path(config_dir) if config_dir else project_root / "config"
    try:
        return (base_dir / DEVICE_ID_FILE).read_text(encoding='utf-8').strip()
    except OSError:
        return ''


# ============ CLI ============


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Trae CN 账号导入工具')
    parser.add_argument('--path', help='指定 cockpit-tools 数据目录或账号 JSON 文件路径')
    parser.add_argument('--list', action='store_true', help='仅预览待导入账号，不写入配置文件')
    parser.add_argument('--config', help=f'指定配置文件路径，默认 {CONFIG_PATH}')
    parser.add_argument('--device-id', action='store_true', help='仅解析并打印本机签到设备 ID')
    args = parser.parse_args()

    if args.device_id:
        device_id = get_or_create_device_id(
            Path(args.config).parent if args.config else None)
        print(device_id)
        return

    config_path = Path(args.config) if args.config else CONFIG_PATH

    if args.path:
        source = Path(args.path).expanduser()
        if not source.exists():
            print(f"❌ 路径不存在: {source}")
            sys.exit(1)

        if source.is_dir():
            # 目录可能是 cockpit 数据目录，也可能是 trae_accounts 目录本身
            source_holder = source.parent if source.name == ACCOUNTS_DIR_NAME else source
            raw_accounts = load_accounts_from_cockpit_dir(source_holder)
        else:
            raw_accounts = load_accounts_from_json_file(source)

        print(f"📂 来源: {source}")
        accounts = [convert_account(r) for r in raw_accounts]
        accounts = [a for a in accounts if a]
        accounts = _dedupe_accounts(accounts)
    else:
        print("🔍 正在自动探测官方 Trae 客户端与 cockpit-tools 数据目录...")
        accounts = collect_accounts()

    if not accounts:
        print("❌ 未找到任何包含 access_token 的 CN 账号数据")
        sys.exit(1)

    print(f"\n共解析到 {len(accounts)} 个账号:")
    for idx, account in enumerate(accounts, 1):
        token_preview = account['access_token'][:12] + '...'
        print(f"  {idx}. {account['account_name']} | user_id: {account.get('user_id', '-')} "
              f"| token: {token_preview}")

    if args.list:
        print("\n👀 预览模式，未写入配置文件")
        return

    stats = merge_into_config(accounts, config_path)
    print(f"\n✅ 导入完成: 新增 {stats['added']} 个，更新 {stats['updated']} 个")
    print(f"📝 配置文件: {config_path}")


def load_accounts_from_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """从单个 JSON 文件读取账号，支持单对象、数组以及 {"accounts": [...]} 结构"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ 读取文件失败: {e}")
        return []

    if isinstance(data, dict):
        if data.get('ciphertext'):
            key_path = find_secure_key(file_path.parent)
            if key_path:
                try:
                    key = base64.b64decode(key_path.read_text(encoding='utf-8').strip())
                    dec = decrypt_record(data, key)
                    if dec:
                        data = dec
                except Exception as e:
                    print(f"⚠️  解密文件 {file_path.name} 失败: {e}")
        if isinstance(data.get('accounts'), list):
            data = data['accounts']
        elif isinstance(data.get('trae'), dict) and isinstance(data['trae'].get('accounts'), list):
            data = data['trae']['accounts']
        else:
            data = [data]

    if not isinstance(data, list):
        return []

    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # 项目配置格式可直接导入（不含 trae_auth_raw）
        if item.get('access_token'):
            account = {
                'user_id': str(item.get('user_id') or item.get('id') or ''),
                'nickname': item.get('nickname') or item.get('account_name') or item.get('email') or '',
                'email': item.get('email') or 'unknown',
                'access_token': item['access_token'],
                'expires_at': item.get('expires_at'),
            }
            if item.get('device_id'):
                account['device_id'] = str(item['device_id'])
            result.append(account)
    return result


def _dedupe_accounts(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 user_id 去重，保留 expires_at 最新者"""
    result: List[Dict[str, Any]] = []
    best_expires: Dict[str, int] = {}
    seen: Dict[str, int] = {}
    for account in accounts:
        identity = account_identity(account)
        if identity:
            if identity in seen:
                if not _merge_best_expires(account, best_expires):
                    continue
                result[seen[identity]] = account
                continue
            seen[identity] = len(result)
            _merge_best_expires(account, best_expires)
        result.append(account)
    return result


if __name__ == '__main__':
    main()
