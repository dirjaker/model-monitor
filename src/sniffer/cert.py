"""
证书管理模块
为 mitmproxy 生成和管理 CA 证书。
"""

import os
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# 证书存储路径
CERT_DIR = Path.home() / ".model-monitor" / "certs"
CA_CERT = CERT_DIR / "mitmproxy-ca-cert.pem"
CA_KEY = CERT_DIR / "mitmproxy-ca.key"


def ensure_cert() -> Path:
    """确保证书存在，不存在则生成"""
    if CA_CERT.exists() and CA_KEY.exists():
        logger.debug("CA 证书已存在: %s", CA_CERT)
        return CA_CERT

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("正在生成 CA 证书...")

    try:
        # 尝试使用 mitmproxy 的证书工具
        result = subprocess.run(
            ["mitmdump", "--set", f"confdir={CERT_DIR}", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if CA_CERT.exists():
            logger.info("CA 证书已通过 mitmproxy 生成: %s", CA_CERT)
            return CA_CERT
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 使用 openssl 生成自签名证书
    _generate_self_signed()
    return CA_CERT


def _generate_self_signed() -> None:
    """使用 openssl 生成自签名 CA 证书"""
    logger.info("使用 openssl 生成自签名 CA 证书")

    # 生成 CA 私钥
    subprocess.run(
        [
            "openssl", "genrsa",
            "-out", str(CA_KEY),
            "2048",
        ],
        check=True,
        capture_output=True,
    )

    # 生成 CA 证书
    subprocess.run(
        [
            "openssl", "req",
            "-x509",
            "-new",
            "-nodes",
            "-key", str(CA_KEY),
            "-sha256",
            "-days", "3650",
            "-out", str(CA_CERT),
            "-subj", "/C=CN/ST=Beijing/L=Beijing/O=ModelMonitor/CN=ModelMonitor CA",
        ],
        check=True,
        capture_output=True,
    )

    # 设置权限
    os.chmod(str(CA_KEY), 0o600)
    os.chmod(str(CA_CERT), 0o644)

    logger.info("CA 证书已生成: %s", CA_CERT)
    logger.info("如需信任此证书，请将 %s 添加到系统信任存储", CA_CERT)


def install_cert_macos() -> bool:
    """在 macOS 上安装证书到系统钥匙串"""
    if not CA_CERT.exists():
        ensure_cert()

    try:
        subprocess.run(
            [
                "sudo", "security", "add-trusted-cert",
                "-d",
                "-r", "trustRoot",
                "-k", "/Library/Keychains/System.keychain",
                str(CA_CERT),
            ],
            check=True,
            capture_output=True,
        )
        logger.info("证书已安装到 macOS 系统钥匙串")
        return True
    except subprocess.SubprocessError as e:
        logger.error("安装证书失败: %s", e)
        return False


def get_cert_info() -> dict[str, str]:
    """获取证书信息"""
    if not CA_CERT.exists():
        return {"status": "未生成", "path": str(CA_CERT)}

    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", str(CA_CERT), "-noout", "-subject", "-dates"],
            capture_output=True, text=True, timeout=5,
        )
        return {
            "status": "已存在",
            "path": str(CA_CERT),
            "info": result.stdout.strip(),
        }
    except subprocess.SubprocessError:
        return {"status": "已存在", "path": str(CA_CERT)}
