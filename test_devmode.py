"""
在 Mac 上直接测试开发者模式开启流程。
用法：连接 iPhone，运行 python test_devmode.py
"""
import time
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService

HOSTNAME = 'DevImageWin'

print("=" * 50)
print("开发者模式测试脚本")
print("=" * 50)

# 第 1 步：连接设备
print("\n[1] 连接设备...")
lockdown = create_using_usbmux(connection_type='USB', local_hostname=HOSTNAME)
udid = lockdown.udid
name = lockdown.all_values.get('DeviceName', '未知')
version = lockdown.product_version
print(f"    设备: {name}")
print(f"    iOS:  {version}")
print(f"    UDID: {udid}")

# 第 2 步：检查开发者模式状态
print("\n[2] 检查开发者模式状态...")
try:
    status = lockdown.developer_mode_status
    print(f"    developer_mode_status = {status}")
    if status:
        print("    >>> 开发者模式已开启，无需操作")
        exit(0)
except Exception as e:
    print(f"    获取状态失败: {e}")
    print("    继续尝试开启...")

# 第 3 步：发送开启命令
print("\n[3] 发送开启开发者模式命令 (enable_post_restart=False)...")
amfi = AmfiService(lockdown)
try:
    amfi.enable_developer_mode(enable_post_restart=False)
    print("    命令发送成功，设备将重启")
except Exception as e:
    print(f"    命令失败: {e}")
    exit(1)

# 第 4 步：等待设备断开
print("\n[4] 等待设备断开连接...")
disconnected = False
for i in range(30):
    try:
        create_using_usbmux(serial=udid, connection_type='USB', local_hostname=HOSTNAME)
        print(f"    {i+1}s - 设备仍在线")
        time.sleep(1)
    except Exception as e:
        print(f"    {i+1}s - 设备已断开: {type(e).__name__}")
        disconnected = True
        break

if not disconnected:
    print("    >>> 30秒内设备未断开，可能未重启")
    exit(1)

# 第 5 步：等待设备重连
print("\n[5] 等待设备重启后重连（请解锁手机）...")
new_lockdown = None
for i in range(60):
    try:
        new_lockdown = create_using_usbmux(
            serial=udid, connection_type='USB', local_hostname=HOSTNAME
        )
        print(f"    {i*3}s - 设备已重连!")
        break
    except Exception as e:
        print(f"    {i*3}s - 等待中... ({type(e).__name__})")
        time.sleep(3)

if new_lockdown is None:
    print("    >>> 180秒内未能重连")
    exit(1)

# 第 6 步：等待服务就绪
print("\n[6] 等待系统服务就绪 (5秒)...")
time.sleep(5)

# 第 7 步：发送确认
print("\n[7] 发送 enable_developer_mode_post_restart()...")
try:
    new_amfi = AmfiService(new_lockdown)
    new_amfi.enable_developer_mode_post_restart()
    print("    确认命令发送成功!")
except Exception as e:
    print(f"    确认失败: {type(e).__name__}: {e}")

# 第 8 步：验证
print("\n[8] 验证开发者模式状态...")
time.sleep(3)
try:
    check = create_using_usbmux(serial=udid, connection_type='USB', local_hostname=HOSTNAME)
    status = check.developer_mode_status
    print(f"    developer_mode_status = {status}")
    if status:
        print("    >>> 开发者模式已成功开启!")
    else:
        print("    >>> 开发者模式仍未开启")
except Exception as e:
    print(f"    验证失败（设备可能在二次重启中）: {e}")
    print("    请等设备重启完成后手动检查")

print("\n" + "=" * 50)
print("测试完成")
