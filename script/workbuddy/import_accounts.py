#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy账号导入工具

将本机已有的 WorkBuddy 账号批量导入到本项目的 config/token.json 中的 workbuddy 节点。

支持的导入来源：
1. 官方 WorkBuddy 客户端（自动探测，读取当前登录账号，逻辑对齐 cockpit-tools 原版本机导入）
2. cockpit-tools 数据目录（批量导入其管理的全部账号）
3. 指定账号 JSON 文件，或包含账号数组的 JSON 文件

官方客户端凭据存储（对齐 cockpit-tools 实现）：
- 数据库：%APPDATA%/WorkBuddy/User/globalStorage/state.vscdb（macOS/Linux 对应各自目录）
- 读取 ItemTable 中 secret://{"extensionId":"tencent-cloud.coding-copilot","key":"planning-genie.new.accessTokencn"}
- Windows：Local State 的 os_crypt.encrypted_key 经 DPAPI 解出 AES 密钥，AES-256-GCM（v10 前缀）
- macOS：Keychain "WorkBuddy Safe Storage" + PBKDF2-SHA1 派生密钥，AES-128-CBC（v10 前缀）
- token 兼容 "uid+token" 拼接格式

使用示例：
    python import_accounts.py                      # 官方客户端 + cockpit-tools 自动探测导入
    python import_accounts.py --list               # 仅预览，不写入配置
    python import_accounts.py --path D:/xxx.json   # 从指定文件导入
    python import_accounts.py --path D:/xxx/dir    # 从指定目录导入
"""

import argparse
import base64
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = project_root / "config" / "token.json"

# cockpit-tools 中的账号索引文件与详情目录名
ACCOUNTS_INDEX_FILE = "workbuddy_accounts.json"
ACCOUNTS_DIR_NAME = "workbuddy_accounts"
# 加密账号使用的本地密钥文件名
KEY_FILE_NAME = "secure-account-storage.key"

# 官方 WorkBuddy 客户端的 Secret Storage 标识（与 cockpit-tools 原版一致）
OFFICIAL_EXTENSION_ID = 'tencent-cloud.coding-copilot'
OFFICIAL_SECRET_KEY = 'planning-genie.new.accessTokencn'

try:
    from Crypto.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# HAS_CRYPTO 为 False 时只提示一次，避免逐文件刷屏
_crypto_warned = False


def _warn_no_crypto() -> None:
    """遇到加密账号但缺少 pycryptodome 时给出一次性安装提示"""
    global _crypto_warned
    if not _crypto_warned:
        _crypto_warned = True
        print("⚠️  检测到加密存储的账号，但缺少 pycryptodome，无法解密（pip install pycryptodome）")


def find_official_client_db() -> Optional[Path]:
    """
    定位官方 WorkBuddy 客户端凭据数据库（对齐 cockpit-tools get_default_workbuddy_state_db_path）

    Returns:
        Optional[Path]: state.vscdb 路径，未找到返回 None
    """
    roots: List[Path] = []
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA') or str(Path.home() / 'AppData' / 'Roaming')
        roots.append(Path(appdata) / 'WorkBuddy')
    elif sys.platform == 'darwin':
        roots.append(Path.home() / 'Library' / 'Application Support' / 'WorkBuddy')
    else:
        xdg = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
        roots.append(Path(xdg) / 'WorkBuddy')

    for root in roots:
        db_path = root / 'User' / 'globalStorage' / 'state.vscdb'
        if db_path.is_file():
            return db_path
    return None


def _dpapi_decrypt(data: bytes) -> bytes:
    """Windows DPAPI CryptUnprotectData（对齐 cockpit-tools dpapi_decrypt）"""
    import ctypes

    class _BLOB(ctypes.Structure):
        _fields_ = [('cbData', ctypes.c_uint), ('pbData', ctypes.c_void_p)]

    buf = ctypes.create_string_buffer(bytes(data), len(data))
    src = _BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    dst = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)):
        raise OSError('DPAPI CryptUnprotectData 调用失败')
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        if dst.pbData:
            ctypes.windll.kernel32.LocalFree(ctypes.c_void_p(dst.pbData))


def _decrypt_windows_v10(data_root: Path, encrypted: bytes) -> str:
    """
    Windows 平台解密：Local State 的 DPAPI 加密密钥 + AES-256-GCM
    （对齐 cockpit-tools get_windows_encryption_key + decrypt_windows_gcm_v10）
    """
    if len(encrypted) < 31 or encrypted[:3] != b'v10':
        raise ValueError('密文不是 Windows v10 格式')

    local_state_path = data_root / 'Local State'
    local_state = json.loads(local_state_path.read_text(encoding='utf-8'))
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
    if encrypted_key[:5] != b'DPAPI':
        raise ValueError('encrypted_key 前缀不是 DPAPI')

    key = _dpapi_decrypt(encrypted_key[5:])
    cipher = AES.new(key, AES.MODE_GCM, nonce=encrypted[3:15])
    plain = cipher.decrypt_and_verify(encrypted[15:-16], encrypted[-16:])
    return plain.decode('utf-8')


def _decrypt_macos_v10(data_root: Path, encrypted: bytes) -> str:
    """
    macOS 平台解密：Keychain 中的 WorkBuddy Safe Storage 密码 + PBKDF2-SHA1 派生密钥 + AES-128-CBC
    （对齐 cockpit-tools get_macos_safe_storage_password + pbkdf2_sha1_key + decrypt_cbc_prefixed）
    """
    if encrypted[:3] != b'v10':
        raise ValueError('密文不是 macOS v10 格式')

    candidates = ['WorkBuddy', 'workbuddy', 'WorkBuddy Key', None, 'WorkBuddy Safe Storage']
    for account in candidates:
        cmd = ['security', 'find-generic-password', '-w', '-s', 'WorkBuddy Safe Storage']
        if account:
            cmd += ['-a', account]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            continue
        password = result.stdout.strip()
        key = hashlib.pbkdf2_hmac('sha1', password.encode('utf-8'), b'saltysalt', 1003, dklen=16)
        cipher = AES.new(key, AES.MODE_CBC, iv=b' ' * 16)
        plain = cipher.decrypt(encrypted[3:])
        pad_len = plain[-1]
        if 1 <= pad_len <= 16 and plain[-pad_len:] == bytes([pad_len]) * pad_len:
            return plain[:-pad_len].decode('utf-8')
    raise OSError('未能从 Keychain 读取 WorkBuddy Safe Storage 密码')


def read_official_client_secret(db_path: Path) -> Optional[str]:
    """
    从 state.vscdb 读取并解密 WorkBuddy Secret Storage 值
    （对齐 cockpit-tools read_secret_storage_value_with_data_root_and_mode + decode_secret_storage_value）
    """
    item_key = f'secret://{{"extensionId":"{OFFICIAL_EXTENSION_ID}","key":"{OFFICIAL_SECRET_KEY}"}}'
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute('SELECT value FROM ItemTable WHERE key = ?', (item_key,)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    raw = row[0]

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    # Node Buffer JSON 形态：{"type":"Buffer","data":[...]}，取出密文字节后按平台解密
    if isinstance(parsed, dict) and isinstance(parsed.get('data'), list):
        encrypted = bytes(parsed['data'])
        data_root = db_path.parent.parent.parent
        if sys.platform == 'win32':
            return _decrypt_windows_v10(data_root, encrypted)
        if sys.platform == 'darwin':
            return _decrypt_macos_v10(data_root, encrypted)
        raise NotImplementedError(
            'Linux 平台暂不支持解密官方客户端凭据，请改用 cockpit-tools 或手动导入')
    if isinstance(parsed, str):
        return parsed
    return raw


def _pick_local_token(value: Any) -> Optional[str]:
    """宽松提取 access token（对齐 cockpit-tools parse_local_access_token）"""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            found = _pick_local_token(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        for key in ('token', 'access_token', 'accessToken'):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        auth = value.get('auth')
        if isinstance(auth, dict):
            for key in ('accessToken', 'access_token'):
                v = auth.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        for key in ('session', 'data'):
            found = _pick_local_token(value.get(key))
            if found:
                return found
    return None


def account_from_official_secret(secret: str) -> Optional[Dict[str, Any]]:
    """
    从解密后的 secret 提取账号信息（对齐 cockpit-tools build_local_import_payload）

    兼容 JSON（含 auth/account 对象）与纯 token 字符串两种形态，
    token 兼容 "uid+token" 拼接格式。

    Returns:
        Optional[Dict[str, Any]]: convert_account 兼容的原始账号结构，解析失败返回 None
    """
    try:
        parsed: Any = json.loads(secret)
        if not isinstance(parsed, dict):
            parsed = None
    except (json.JSONDecodeError, TypeError):
        parsed = None

    raw_token = _pick_local_token(parsed) if parsed else None
    if not raw_token:
        raw_token = secret.strip() or None
    if not raw_token:
        return None

    # 拆分 "uid+token" 拼接格式（对齐 extract_local_workbuddy_token_parts）
    uid_from_token: Optional[str] = None
    if '+' in raw_token:
        prefix, _, suffix = raw_token.partition('+')
        suffix = suffix.strip()
        if not suffix:
            return None
        uid_from_token = prefix.strip() or None
        raw_token = suffix

    root = parsed or {}
    account = root.get('account') if isinstance(root.get('account'), dict) else {}
    auth = root.get('auth') if isinstance(root.get('auth'), dict) else {}

    def pick(obj: Dict[str, Any], *keys: str) -> Optional[str]:
        for key in keys:
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    uid = pick(root, 'uid') or pick(account, 'uid', 'id') or uid_from_token
    nickname = pick(root, 'nickname', 'name') or pick(account, 'nickname', 'label')
    email = (pick(root, 'email') or pick(account, 'email') or pick(auth, 'email')
             or nickname or uid or 'unknown')
    enterprise_id = (pick(root, 'enterpriseId', 'enterprise_id')
                     or pick(account, 'enterpriseId', 'enterprise_id'))
    refresh_token = (pick(root, 'refreshToken', 'refresh_token')
                     or pick(auth, 'refreshToken', 'refresh_token'))
    domain = pick(root, 'domain') or pick(auth, 'domain')

    raw: Dict[str, Any] = {
        'nickname': nickname or email,
        'email': email,
        'access_token': raw_token,
    }
    if refresh_token:
        raw['refresh_token'] = refresh_token
    if uid:
        raw['uid'] = uid
    if enterprise_id:
        raw['enterprise_id'] = enterprise_id
    if domain:
        raw['domain'] = domain
    return raw


def load_accounts_from_official_client(quiet: bool = False) -> List[Dict[str, Any]]:
    """
    从官方 WorkBuddy 客户端读取当前登录账号
    （对齐 cockpit-tools import_payload_from_local，单账号）

    Returns:
        List[Dict[str, Any]]: 原始账号数据列表，未找到返回空列表
    """
    db_path = find_official_client_db()
    if not db_path:
        return []
    try:
        secret = read_official_client_secret(db_path)
    except Exception as e:
        if not quiet:
            print(f"⚠️  读取官方客户端凭据失败: {e}")
        return []
    if not secret:
        return []
    account = account_from_official_secret(secret)
    return [account] if account else []


def find_cockpit_data_dirs() -> List[Path]:
    """
    自动探测本机可能存在的 cockpit-tools 数据目录

    Returns:
        List[Path]: 包含 WorkBuddy 账号数据的候选目录列表
    """
    candidates: List[Path] = []
    home = Path.home()

    # 各平台应用数据根目录
    roots: List[Path] = []
    if sys.platform == 'win32':
        for env_key in ('APPDATA', 'LOCALAPPDATA'):
            value = os.environ.get(env_key)
            if value:
                roots.append(Path(value))
        # 家目录本身（cockpit-tools 数据可能在 C:/Users/xxx/.antigravity_cockpit）
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
                    if (child / ACCOUNTS_INDEX_FILE).exists() or (child / ACCOUNTS_DIR_NAME).is_dir():
                        candidates.append(child)
        except PermissionError:
            continue

    return candidates


def find_secure_key(source_dir: Path) -> Optional[Path]:
    """
    为给定账号来源目录查找解密用的本地密钥文件

    优先在来源目录及其上级目录查找，最后回退到常见的家目录路径。

    Args:
        source_dir (Path): 账号来源目录（可能是 cockpit 数据目录或 workbuddy_accounts 目录）

    Returns:
        Optional[Path]: 密钥文件路径，未找到返回 None
    """
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

    # 回退：家目录下的常见位置
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
    """
    使用本地密钥解密 AES-256-GCM 加密的账号记录

    Args:
        enc (Dict[str, Any]): 含 ciphertext/nonce 的加密记录
        key (bytes): 32 字节 AES 密钥

    Returns:
        Optional[Dict[str, Any]]: 解密后的明文账号数据，失败返回 None
    """
    if not HAS_CRYPTO:
        _warn_no_crypto()
        return None
    try:
        nonce = base64.b64decode(enc['nonce'])
        ct = base64.b64decode(enc['ciphertext'])
        # GCM 认证标签为密文末尾 16 字节
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plain = cipher.decrypt_and_verify(ct[:-16], ct[-16:])
        return json.loads(plain.decode('utf-8'))
    except Exception as e:
        print(f"⚠️  解密失败: {e}")
        return None


def load_accounts_from_dir(directory: Path, quiet: bool = False) -> List[Dict[str, Any]]:
    """
    从目录中读取 WorkBuddy 账号详情

    兼容两种传入方式：cockpit-tools 数据目录，或直接是 workbuddy_accounts 目录。
    同时兼容明文与 AES-256-GCM 加密两种存储格式。

    Args:
        directory (Path): 目录路径
        quiet (bool): True 时不输出警告信息

    Returns:
        List[Dict[str, Any]]: 原始账号数据列表
    """
    accounts_dir = directory / ACCOUNTS_DIR_NAME
    if not accounts_dir.is_dir():
        accounts_dir = directory

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
        if json_file.name == ACCOUNTS_INDEX_FILE:
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if not quiet:
                print(f"⚠️  跳过无法解析的文件 {json_file.name}: {e}")
            continue

        # 加密格式：含 ciphertext 字段
        if isinstance(data, dict) and data.get('ciphertext'):
            if not key:
                if not quiet:
                    print(f"⚠️  跳过加密账号 {json_file.name}: 未找到解密密钥 {KEY_FILE_NAME}")
                continue
            data = decrypt_record(data, key)
            if not data:
                continue

        if isinstance(data, dict) and data.get('access_token'):
            accounts.append(data)

    return accounts


def load_accounts_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    从单个 JSON 文件读取账号，支持单对象、数组以及 {"accounts": [...]} 结构

    Args:
        file_path (Path): JSON 文件路径

    Returns:
        List[Dict[str, Any]]: 原始账号数据列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ 读取文件失败: {e}")
        return []

    if isinstance(data, dict):
        # 单文件加密记录
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
        else:
            data = [data]

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict) and item.get('access_token')]


def convert_account(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    将 cockpit-tools 账号结构转换为本项目配置结构

    Args:
        raw (Dict[str, Any]): cockpit-tools 的账号数据

    Returns:
        Optional[Dict[str, Any]]: 转换后的账号配置，缺少令牌时返回None
    """
    access_token = raw.get('access_token')
    if not access_token:
        return None

    account_name = raw.get('nickname') or raw.get('email') or raw.get('id') or '未命名账号'

    account: Dict[str, Any] = {
        'account_name': account_name,
        'access_token': access_token,
    }

    # 可选字段仅在有值时写入，避免配置中出现大量空串
    for key in ('refresh_token', 'uid', 'enterprise_id', 'domain'):
        value = raw.get(key)
        if value:
            account[key] = value

    return account


def account_identity(account: Dict[str, Any]) -> str:
    """
    生成账号唯一标识，用于导入时去重

    Args:
        account (Dict[str, Any]): 账号配置

    Returns:
        str: 唯一标识
    """
    return (account.get('uid') or account.get('email') or account.get('account_name') or '').strip().lower()


def merge_into_config(new_accounts: List[Dict[str, Any]], config_path: Path) -> Dict[str, int]:
    """
    将账号合并写入配置文件的 workbuddy 节点

    已存在的账号会更新令牌，不存在的账号追加写入

    Args:
        new_accounts (List[Dict[str, Any]]): 待导入的账号列表
        config_path (Path): 配置文件路径

    Returns:
        Dict[str, int]: 包含added和updated数量的统计字典
    """
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}

    workbuddy_node = config_data.setdefault('workbuddy', {})
    existing: List[Dict[str, Any]] = workbuddy_node.setdefault('accounts', [])

    index_map = {account_identity(acc): idx for idx, acc in enumerate(existing) if account_identity(acc)}

    added = 0
    updated = 0

    for account in new_accounts:
        identity = account_identity(account)
        if identity and identity in index_map:
            target = existing[index_map[identity]]
            # 保留用户自定义的账号名称，只更新令牌等认证信息
            for key, value in account.items():
                if key == 'account_name':
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
    自动探测本机账号来源并采集账号（已转换、去重）

    来源顺序：cockpit-tools 数据目录（全部账号）→ 官方 WorkBuddy 客户端（当前登录账号）。
    官方客户端放在最后处理：其令牌来自用户最近一次登录会话（服务端单会话策略下
    旧的 refresh 链已作废），同 uid 时后处理的官方令牌会覆盖 cockpit 侧的失效令牌。

    Args:
        quiet (bool): True 时不输出来源提示

    Returns:
        List[Dict[str, Any]]: 转换后的账号配置列表，无可用来源时返回空列表
    """
    log = (lambda *a, **k: None) if quiet else print
    raw_accounts: List[Dict[str, Any]] = []

    for candidate in find_cockpit_data_dirs():
        found = load_accounts_from_dir(candidate, quiet=quiet)
        if found:
            log(f"📂 来源: {candidate} (发现 {len(found)} 个账号)")
            raw_accounts.extend(found)

    official = load_accounts_from_official_client(quiet=quiet)
    if official:
        log("📂 来源: 官方 WorkBuddy 客户端 (发现 1 个账号)")
        raw_accounts.extend(official)

    accounts: List[Dict[str, Any]] = []
    seen = set()
    for raw in raw_accounts:
        converted = convert_account(raw)
        if not converted:
            continue
        identity = account_identity(converted)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        accounts.append(converted)

    return accounts


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='WorkBuddy账号导入工具')
    parser.add_argument('--path', help='指定 cockpit-tools 数据目录或账号 JSON 文件路径')
    parser.add_argument('--list', action='store_true', help='仅预览待导入账号，不写入配置文件')
    parser.add_argument('--config', help=f'指定配置文件路径，默认 {CONFIG_PATH}')
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else CONFIG_PATH

    if args.path:
        source = Path(args.path).expanduser()
        if not source.exists():
            print(f"❌ 路径不存在: {source}")
            sys.exit(1)

        if source.is_dir():
            raw_accounts = load_accounts_from_dir(source)
        else:
            raw_accounts = load_accounts_from_file(source)

        print(f"📂 来源: {source}")

        accounts: List[Dict[str, Any]] = []
        seen = set()
        for raw in raw_accounts:
            converted = convert_account(raw)
            if not converted:
                continue
            identity = account_identity(converted)
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            accounts.append(converted)
    else:
        print("🔍 正在自动探测官方 WorkBuddy 客户端与 cockpit-tools 数据目录...")
        accounts = collect_accounts()

    if not accounts:
        print("❌ 未找到任何包含 access_token 的账号数据")
        sys.exit(1)

    print(f"\n共解析到 {len(accounts)} 个账号:")
    for idx, account in enumerate(accounts, 1):
        token_preview = account['access_token'][:12] + '...'
        print(f"  {idx}. {account['account_name']} | {account.get('email', '-')} | token: {token_preview}")

    if args.list:
        print("\n👀 预览模式，未写入配置文件")
        return

    stats = merge_into_config(accounts, config_path)
    print(f"\n✅ 导入完成: 新增 {stats['added']} 个，更新 {stats['updated']} 个")
    print(f"📝 配置文件: {config_path}")


if __name__ == '__main__':
    main()
