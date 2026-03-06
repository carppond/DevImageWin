"""
准备 DDI 数据：从已安装的 developer_disk_image 包复制镜像文件到项目目录。
打包前运行一次即可：python prepare_ddi.py
"""
import shutil
import sys
from pathlib import Path

def find_ddi_source():
    """查找已安装的 developer_disk_image 包路径"""
    try:
        import developer_disk_image
        return Path(developer_disk_image.__file__).parent
    except ImportError:
        print("错误：未安装 developer_disk_image 包。")
        print("请运行：pip install developer-disk-image")
        sys.exit(1)

def main():
    src = find_ddi_source()
    dest = Path(__file__).parent / 'ddi_data'

    src_dev = src / 'DeveloperDiskImages'
    src_pers = src / 'PersonalizedImages'

    if not src_dev.exists():
        print(f"错误：{src_dev} 不存在")
        sys.exit(1)

    # 清理旧数据
    if dest.exists():
        print(f"清理旧数据：{dest}")
        shutil.rmtree(dest)

    # 复制 DeveloperDiskImages
    dest_dev = dest / 'DeveloperDiskImages'
    print(f"复制 DeveloperDiskImages...")
    shutil.copytree(src_dev, dest_dev)
    versions = [d.name for d in dest_dev.iterdir() if d.is_dir()]
    print(f"  已复制 {len(versions)} 个版本：{', '.join(sorted(versions))}")

    # 复制 PersonalizedImages
    if src_pers.exists():
        dest_pers = dest / 'PersonalizedImages'
        print(f"复制 PersonalizedImages...")
        shutil.copytree(src_pers, dest_pers)

    total_size = sum(f.stat().st_size for f in dest.rglob('*') if f.is_file())
    print(f"\n完成！总大小：{total_size / 1024 / 1024:.1f} MB")
    print(f"数据目录：{dest}")

if __name__ == '__main__':
    main()
