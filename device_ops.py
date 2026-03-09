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
from pymobiledevice3.services.heartbeat import HeartbeatService
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


async def enable_dev_mode(udid):
    """
    开启开发者模式。
    手动处理重启后重连，避免 pymobiledevice3 内部重连时的 WinError 52。
    """
    try:
        logger.info(f"enable_dev_mode: 开始, udid={udid}")
        lockdown = await _create_lockdown(udid)
        amfi = AmfiService(lockdown)

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

        # 第 4 步：等几秒让系统服务完全就绪
        logger.info("enable_dev_mode: [4/5] 等待服务就绪 (5秒)...")
        time.sleep(5)

        # 第 5 步：确认开发者模式
        logger.info("enable_dev_mode: [5/5] 发送 post_restart 确认...")
        new_amfi = AmfiService(new_lockdown)
        result = new_amfi.enable_developer_mode_post_restart()
        # 兼容 async 版本
        if asyncio.iscoroutine(result):
            await result
        logger.info("enable_dev_mode: [5/5] 确认成功!")

        return "开发者模式已成功开启。"

    except DeviceOpsError:
        raise
    except DeviceHasPasscodeSetError:
        raise DeviceOpsError(
            "设备设置了锁屏密码，无法自动开启开发者模式。\n"
            "请在设备上手动开启：\n"
            "设置 → 隐私与安全性 → 开发者模式"
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
    返回成功消息字符串。
    """
    logger.info(f"mount_ddi: 开始, udid={udid}")
    lockdown = await _create_lockdown(udid)
    ios_version = lockdown.product_version
    logger.info(f"mount_ddi: iOS={ios_version}")

    try:
        if Version(ios_version) < Version('17.0'):
            # iOS < 17：使用传统 DeveloperDiskImage
            paths = _find_bundled_ddi(ios_version)
            if paths is None:
                raise DeviceOpsError(
                    f"未找到 iOS {ios_version} 对应的开发者磁盘映像。\n"
                    "当前内置镜像支持 iOS 11.4 ~ 16.7。"
                )
            image_path, sig_path = paths
            mounter = DeveloperDiskImageMounter(lockdown=lockdown)
            await mounter.mount(image_path, sig_path)
        else:
            # iOS 17+：使用个性化 DDI（需要 TSS 签名，需联网）
            paths = _find_bundled_personalized()
            if paths is None:
                raise DeviceOpsError("未找到内置的个性化开发者磁盘映像。")
            image, manifest, trustcache = paths
            await PersonalizedImageMounter(lockdown=lockdown).mount(image, manifest, trustcache)

        return "开发者磁盘映像挂载成功。"

    except AlreadyMountedError:
        return "开发者磁盘映像已挂载，无需重复操作。"
    except DeveloperModeIsNotEnabledError:
        raise DeviceOpsError("挂载失败：开发者模式未开启。\n请先开启开发者模式。")
    except DeviceOpsError:
        raise
    except (RequestsConnectionError, ProxyError, URLError, ConnectionRefusedError, OSError) as e:
        err_str = str(e)
        logger.error(f"mount_ddi: 网络错误: {err_str}")
        raise DeviceOpsError(
            "连接 Apple 服务器失败。\n"
            "iOS 17+ 挂载 DDI 需要联网获取 Apple 签名。\n\n"
            "请检查：\n"
            "1. 电脑是否可以正常上网\n"
            "2. 如果使用了代理（Clash/V2Ray 等），请确保代理软件已启动\n"
            "3. 尝试关闭代理后重试"
        )
    except (ConnectionAbortedError, BrokenPipeError, ConnectionTerminatedError):
        raise DeviceOpsError("设备连接中断。\n请重新检测设备后重试。")
    except Exception as e:
        raise DeviceOpsError(f"挂载开发者磁盘映像时发生错误：{e}")
