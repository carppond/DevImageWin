import asyncio
import logging
import sys
import time
from pathlib import Path
from urllib.error import URLError

from packaging.version import Version
from requests.exceptions import ConnectionError as RequestsConnectionError, ProxyError

from pymobiledevice3.exceptions import (
    AlreadyMountedError,
    AmfiError,
    ConnectionFailedError,
    ConnectionTerminatedError,
    DeveloperModeError,
    DeveloperModeIsNotEnabledError,
    DeviceHasPasscodeSetError,
    NoDeviceConnectedError,
    NotPairedError,
    PairingDialogResponsePendingError,
)
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.services.mobile_image_mounter import (
    DeveloperDiskImageMounter,
    PersonalizedImageMounter,
    MobileImageMounterService,
)

logger = logging.getLogger(__name__)


def _get_bundled_data_dir() -> Path:
    """获取内置数据目录（兼容 PyInstaller 打包和源码运行）"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'ddi_data'
    return Path(__file__).parent / 'ddi_data'


class DeviceOpsError(Exception):
    """带中文错误消息的设备操作异常"""
    pass


async def _create_lockdown(udid=None):
    """创建 USB lockdown 连接，复用连接异常处理逻辑。"""
    logger.info(f"_create_lockdown: udid={udid}")
    try:
        lockdown = await create_using_usbmux(
            identifier=udid, connection_type='USB', local_hostname='DevImageWin'
        )
        logger.info(f"_create_lockdown: 连接成功, udid={lockdown.udid}, version={lockdown.product_version}")
        return lockdown
    except ConnectionFailedError:
        raise DeviceOpsError(
            "无法连接到 usbmuxd 服务。\n"
            "Windows：请确认已安装 iTunes 或 Apple 设备支持。\n"
            "macOS：请确认 usbmuxd 正在运行。"
        )
    except NoDeviceConnectedError:
        raise DeviceOpsError("未检测到已连接的 iOS 设备。\n请通过 USB 连接设备。")
    except PairingDialogResponsePendingError:
        raise DeviceOpsError("请在 iOS 设备上点击「信任」按钮，然后重试。")
    except NotPairedError:
        raise DeviceOpsError("设备未配对。\n请解锁设备并点击「信任此电脑」。")
    except Exception as e:
        raise DeviceOpsError(f"连接设备时发生错误：{e}")


async def detect_device():
    """
    检测 USB 连接的 iOS 设备。
    返回 dict: {name, version, product_type, display_name, udid, dev_mode, ddi_mounted}
    """
    logger.info("detect_device: 开始检测...")
    lockdown = await _create_lockdown()

    all_vals = lockdown.all_values
    ios_version = lockdown.product_version
    logger.info(f"detect_device: 设备={all_vals.get('DeviceName')}, iOS={ios_version}")

    # 检查开发者模式状态
    dev_mode = False
    try:
        dev_mode = await lockdown.get_developer_mode_status()
        logger.info(f"detect_device: developer_mode_status={dev_mode}")
    except Exception as e:
        logger.warning(f"detect_device: 获取开发者模式状态失败: {e}")

    # 检查 DDI 挂载状态
    ddi_mounted = False
    try:
        mounter = MobileImageMounterService(lockdown=lockdown)
        if Version(ios_version) >= Version('17.0'):
            ddi_mounted = await mounter.is_image_mounted('Personalized')
        else:
            ddi_mounted = await mounter.is_image_mounted('Developer')
        logger.info(f"detect_device: ddi_mounted={ddi_mounted}")
    except Exception as e:
        logger.warning(f"detect_device: 获取DDI状态失败: {e}")

    return {
        'name': all_vals.get('DeviceName', '未知'),
        'version': ios_version,
        'product_type': lockdown.product_type,
        'display_name': lockdown.display_name or lockdown.product_type,
        'udid': lockdown.udid,
        'dev_mode': dev_mode,
        'ddi_mounted': ddi_mounted,
    }


async def _wait_for_device_disconnect(udid, timeout=30):
    """等待设备真正断开连接（轮询直到连不上为止）"""
    start = time.time()
    while time.time() - start < timeout:
        elapsed = int(time.time() - start)
        try:
            lk = await create_using_usbmux(
                serial=udid, connection_type='USB', local_hostname='DevImageWin'
            )
            logger.debug(f"_wait_disconnect: {elapsed}s - 设备仍在线")
            await asyncio.sleep(1)
        except Exception as e:
            logger.info(f"_wait_disconnect: {elapsed}s - 设备已断开: {type(e).__name__}")
            return True
    logger.warning(f"_wait_disconnect: {timeout}s 超时，设备未断开")
    return False


async def _wait_for_device_reconnect(udid, timeout=120):
    """等待设备重启后重新连接（轮询，使用自定义 local_hostname）"""
    start = time.time()
    while time.time() - start < timeout:
        elapsed = int(time.time() - start)
        try:
            lockdown = await create_using_usbmux(
                serial=udid, connection_type='USB', local_hostname='DevImageWin'
            )
            logger.info(f"_wait_reconnect: {elapsed}s - 设备已重连!")
            return lockdown
        except Exception as e:
            logger.debug(f"_wait_reconnect: {elapsed}s - 等待中: {type(e).__name__}")
            await asyncio.sleep(3)
    logger.warning(f"_wait_reconnect: {timeout}s 超时")
    return None


async def _verify_device_connection(udid):
    """操作前验证设备连接，失败时给出明确的 USB 相关提示"""
    try:
        lockdown = await create_using_usbmux(
            identifier=udid, connection_type='USB', local_hostname='DevImageWin'
        )
        logger.info(f"_verify_connection: 设备连接正常, udid={udid}")
        return lockdown
    except Exception as e:
        logger.warning(f"_verify_connection: 设备连接失败: {e}")
        raise DeviceOpsError(
            "设备连接已断开。\n"
            "请检查 USB 数据线是否松动，重新插拔后点击「检测设备」。"
        )


# 可重试的连接类异常（含超时）
_RETRYABLE_ERRORS = (
    ConnectionAbortedError,
    BrokenPipeError,
    ConnectionTerminatedError,
    ConnectionResetError,
    asyncio.TimeoutError,
)


async def enable_dev_mode(udid):
    """
    开启开发者模式。
    手动处理重启后重连，避免 pymobiledevice3 内部重连时的 WinError 52。
    """
    try:
        logger.info(f"enable_dev_mode: 开始, udid={udid}")

        # 操作前验证连接
        await _verify_device_connection(udid)
        lockdown = await _create_lockdown(udid)
        amfi = AmfiService(lockdown)

        # 第 0 步：先让「开发者模式」选项在设置中显示出来
        # 即使后续自动开启失败（如有密码），用户也能在设置中找到开关
        logger.info("enable_dev_mode: [0/5] 显示开发者模式选项...")
        try:
            result_reveal = amfi.reveal_developer_mode_option_in_ui()
            if asyncio.iscoroutine(result_reveal):
                await result_reveal
            logger.info("enable_dev_mode: [0/5] 已显示开发者模式选项")
        except Exception as e:
            logger.warning(f"enable_dev_mode: [0/5] reveal 失败（可忽略）: {e}")

        # 第 1 步：发送开启命令（不等待重启后确认）
        logger.info("enable_dev_mode: [1/5] 发送开启命令...")
        await amfi.enable_developer_mode(enable_post_restart=False)
        logger.info("enable_dev_mode: [1/5] 命令发送成功")

        # 第 2 步：等设备真正断开（确认已开始重启）
        logger.info("enable_dev_mode: [2/5] 等待设备断开...")
        disconnected = await _wait_for_device_disconnect(udid, timeout=30)
        logger.info(f"enable_dev_mode: [2/5] 断开结果: {disconnected}")

        # 第 3 步：等设备重启完成后重连
        logger.info("enable_dev_mode: [3/5] 等待设备重连...")
        new_lockdown = await _wait_for_device_reconnect(udid, timeout=120)
        if new_lockdown is None:
            logger.error("enable_dev_mode: [3/5] 重连超时")
            raise DeviceOpsError(
                "设备重启后重连超时。\n"
                "请解锁设备后重新点击「检测设备」。"
            )
        logger.info(f"enable_dev_mode: [3/5] 重连成功, version={new_lockdown.product_version}")

        # 第 4 步：等待服务就绪并发送确认（重试最多 3 次）
        for post_attempt in range(3):
            wait_secs = 5 + post_attempt * 5  # 5s, 10s, 15s
            logger.info(f"enable_dev_mode: [4/5] 等待服务就绪 ({wait_secs}秒)...")
            await asyncio.sleep(wait_secs)

            logger.info(f"enable_dev_mode: [5/5] 发送 post_restart 确认 (尝试 {post_attempt + 1}/3)...")
            try:
                # 重新建立连接，避免使用过期的 lockdown
                fresh_lockdown = await _create_lockdown(udid)
                fresh_amfi = AmfiService(fresh_lockdown)
                result = fresh_amfi.enable_developer_mode_post_restart()
                if asyncio.iscoroutine(result):
                    await result
                logger.info("enable_dev_mode: [5/5] 确认成功!")
                break
            except Exception as e:
                logger.warning(f"enable_dev_mode: [5/5] 确认失败 ({post_attempt + 1}/3): {e}")
                if post_attempt == 2:
                    raise

        return "开发者模式已成功开启。"

    except DeviceOpsError:
        raise
    except DeviceHasPasscodeSetError:
        raise DeviceOpsError(
            "设备设置了锁屏密码，无法自动开启开发者模式。\n\n"
            "已为您显示开发者模式选项，请在设备上手动开启：\n"
            "设置 → 隐私与安全性 → 开发者模式\n\n"
            "开启后设备会自动重启，重启完成并解锁后，\n"
            "点击「检测设备」继续操作。"
        )
    except DeveloperModeError as e:
        raise DeviceOpsError(f"开启开发者模式失败：{e}")
    except AmfiError as e:
        raise DeviceOpsError(f"AMFI 服务错误：{e}")
    except (ConnectionAbortedError, BrokenPipeError, ConnectionTerminatedError):
        raise DeviceOpsError(
            "设备连接中断。\n"
            "请等待设备重启完成后，解锁设备并重新检测。"
        )
    except Exception as e:
        raise DeviceOpsError(f"开启开发者模式时发生错误：{e}")


def _find_bundled_ddi(ios_version_str):
    """
    从内置 DDI 数据中查找匹配的开发者磁盘映像。
    匹配规则：major.minor 版本号匹配。
    返回 (image_path, signature_path) 或 None。
    """
    data_dir = _get_bundled_data_dir() / 'DeveloperDiskImages'
    v = Version(ios_version_str)
    version_key = f'{v.major}.{v.minor}'

    image_path = data_dir / version_key / 'DeveloperDiskImage.dmg'
    sig_path = data_dir / version_key / 'DeveloperDiskImage.dmg.signature'

    if image_path.exists() and sig_path.exists():
        return image_path, sig_path
    return None


def _find_bundled_personalized():
    """
    从内置数据中获取个性化 DDI 文件路径。
    返回 (image_path, build_manifest_path, trustcache_path) 或 None。
    """
    data_dir = _get_bundled_data_dir() / 'PersonalizedImages' / 'Xcode_iOS_DDI_Personalized'
    image = data_dir / 'Image.dmg'
    manifest = data_dir / 'BuildManifest.plist'
    trustcache = data_dir / 'Image.dmg.trustcache'

    if image.exists() and manifest.exists() and trustcache.exists():
        return image, manifest, trustcache
    return None


async def mount_ddi(udid):
    """
    挂载开发者磁盘映像 (DDI)。
    优先使用内置的 DDI 文件，无需网络下载。
    连接中断或超时时自动重试最多 3 次。
    返回成功消息字符串。
    """
    max_retries = 3
    retry_delay = 3
    mount_timeout = 60  # 单次挂载操作超时秒数

    # 操作前验证连接
    await _verify_device_connection(udid)

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"mount_ddi: 重试 {attempt}/{max_retries - 1}...")

            logger.info(f"mount_ddi: 开始, udid={udid}")
            lockdown = await _create_lockdown(udid)
            ios_version = lockdown.product_version
            logger.info(f"mount_ddi: iOS={ios_version}")

            if Version(ios_version) < Version('17.0'):
                # iOS < 17：使用传统 DeveloperDiskImage
                paths = _find_bundled_ddi(ios_version)
                if paths is None:
                    # 判断是否为 iOS 17+ 版本的 EXE（不含 legacy 镜像）
                    legacy_dir = _get_bundled_data_dir() / 'DeveloperDiskImages'
                    if not legacy_dir.exists():
                        raise DeviceOpsError(
                            f"当前程序为 iOS 17+ 版本，不支持 iOS {ios_version}。\n"
                            "请下载 DevImageWin_Legacy 版本。"
                        )
                    raise DeviceOpsError(
                        f"未找到 iOS {ios_version} 对应的开发者磁盘映像。\n"
                        "当前内置镜像支持 iOS 11.4 ~ 16.7。"
                    )
                image_path, sig_path = paths
                mounter = DeveloperDiskImageMounter(lockdown=lockdown)
                await asyncio.wait_for(
                    mounter.mount(image_path, sig_path),
                    timeout=mount_timeout,
                )
            else:
                # iOS 17+：使用个性化 DDI（需要 TSS 签名，需联网）
                paths = _find_bundled_personalized()
                if paths is None:
                    # 判断是否为 Legacy 版本的 EXE（不含 personalized 镜像）
                    personalized_dir = _get_bundled_data_dir() / 'PersonalizedImages'
                    if not personalized_dir.exists():
                        raise DeviceOpsError(
                            f"当前程序为 Legacy 版本，不支持 iOS {ios_version}。\n"
                            "请下载 DevImageWin_iOS17+ 版本。"
                        )
                    raise DeviceOpsError("未找到内置的个性化开发者磁盘映像。")
                image, manifest, trustcache = paths
                await asyncio.wait_for(
                    PersonalizedImageMounter(lockdown=lockdown).mount(image, manifest, trustcache),
                    timeout=mount_timeout,
                )

            return "开发者磁盘映像挂载成功。"

        except AlreadyMountedError:
            return "开发者磁盘映像已挂载，无需重复操作。"
        except DeveloperModeIsNotEnabledError:
            raise DeviceOpsError("挂载失败：开发者模式未开启。\n请先开启开发者模式。")
        except DeviceOpsError:
            raise
        except (RequestsConnectionError, ProxyError, URLError, ConnectionRefusedError) as e:
            logger.error(f"mount_ddi: 网络错误: {e}")
            raise DeviceOpsError(
                "连接 Apple 服务器失败。\n"
                "iOS 17+ 挂载 DDI 需要联网获取 Apple 签名。\n\n"
                "请检查：\n"
                "1. 电脑是否可以正常上网\n"
                "2. 如果使用了代理（Clash/V2Ray 等），请确保代理软件已启动\n"
                "3. 尝试关闭代理后重试"
            )
        except _RETRYABLE_ERRORS as e:
            if attempt < max_retries - 1:
                err_type = "超时" if isinstance(e, asyncio.TimeoutError) else f"连接中断 ({type(e).__name__})"
                logger.warning(
                    f"mount_ddi: {err_type}，"
                    f"{retry_delay}秒后重试 ({attempt + 1}/{max_retries - 1})"
                )
                await asyncio.sleep(retry_delay)
                continue
            raise DeviceOpsError(
                "挂载操作超时或连接中断，已重试仍然失败。\n"
                "请检查 USB 数据线是否松动，重新插拔后重试。"
            )
        except Exception as e:
            raise DeviceOpsError(f"挂载开发者磁盘映像时发生错误：{e}")
