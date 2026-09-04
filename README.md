# DataMax-zfs - ZFS Web Management Interface

A modern web-based management interface for ZFS pools, datasets, snapshots, and SMART disk monitoring built with Python FastAPI and HTMX.

## 功能详细介绍

DataMax-zfs 是一个面向 ZFS 的 Web 管理界面，通过浏览器即可完成存储池、数据集、快照、数据复制和磁盘健康等日常运维操作。界面采用 Doubao 浅色冷调设计体系，支持宽屏自适应布局、主题切换和圆角/直角/八边形三种外观风格。

### 仪表盘

- 展示主机系统信息、内存与 CPU 使用情况、存储池概览和健康状态。
- 汇总 ARC 缓存大小、命中率、缓存命中/未命中、MRU/MFU 分布与访问类型。
- 展示 SSD 缓存（L2ARC）命中率、命中/未命中次数、缓存大小与累计读写量。
- 展示数据清洗状态、SMART 状态和各存储池的关键指标。

### 存储池管理

- 支持创建、导入、导出和销毁存储池，销毁需输入完整名称二次确认。
- 支持启动/停止数据清洗、创建/丢弃检查点、查看存储池历史记录。
- 支持查看和修改存储池属性，设置预留空间和挂载点。
- 支持 VDev 管理：添加辅助 VDEV、附加设备、分离设备、更换设备、设备上线/下线。
- 支持导出诊断压缩包，便于故障排查与社区支持。

### 数据集管理

- 支持创建文件系统数据集和卷（zvol），支持加密数据集。
- 支持重命名、克隆、提升（promote）、挂载/卸载以及销毁数据集。
- 支持查看、设置和继承 ZFS 属性，设置配额、预留空间和压缩等。
- 支持加载、卸载、修改和继承加密密钥。
- 支持预览数据集目录中的文件。

### 快照管理

- 支持创建、列表、查看详情、重命名和销毁快照，销毁支持延迟删除。
- 支持回滚、克隆和对比两个快照的差异。
- 支持管理快照保留标记（hold）。
- 集成 Sanoid：支持自动快照模板、数据集策略绑定和 Sanoid 状态查看。

### 数据复制

- 支持原生 ZFS send/receive 手动复制，带源/目标连接测试和命令预览。
- 集成 Syncoid：支持创建、编辑、删除计划任务，展示执行历史和实时进度。
- 支持配置 SSH 连接，用于远程复制。
- 支持 SMTP 邮件通知配置，复制成功或失败时发送提醒。

### 运行观测

- 提供 ARC 摘要和实时 ARC 统计，包含 L2ARC 详情。
- 提供存储池历史、事件、内核日志、系统日志和 ZFS 模块参数查看。
- 提供存储池 I/O、逐 VDEV、逐数据集和系统 I/O 统计。
- 支持搜索 ZFS 日志和查看当前 ZFS 进程。

### SMART 与磁盘健康

- 展示磁盘 SMART 属性、健康状态、温度、自检结果和错误日志。
- 支持手动发起和计划 SMART 自检。
- 支持编辑 smartd 守护进程配置。
- 提供健康检查报告，汇总各磁盘和存储池风险。

### 实用工具

- 计划任务：统一管理数据清洗、SMART 测试、健康检查和数据复制计划。
- 集成 Shell 终端，可直接在浏览器中执行命令。
- 支持在界面中查看和编辑系统文本文件。
- 提供 SSH 连接管理，供数据复制复用。
- 提供审计日志查看与下载，记录认证、ZFS 操作和文件访问。
- 提供服务管理和系统支持包导出。

### 系统与安全

- 通过 PAM 对接本地 Unix 用户账户登录。
- 支持会话超时、登录限流和登录失败锁定。
- 支持主题、外观风格、会话超时等个性化设置。
- 支持导出加密配置备份，并可恢复到当前或迁移后的主机。

### 平台支持

- Linux：支持使用 OpenZFS 的主流发行版。
- FreeBSD：FreeBSD 13.x 及以上版本。
- NetBSD：NetBSD 10.1 和 11.0（amd64）。

应用会自动检测操作系统，并适配对应的命令、服务和调度器。

![webzfs dashboard](screenshots/0.77/dashboard-v0.77.jpg)

***
# Disclaimer
Due to Reddit Drama... I'm making this clear up front. **_This is not a vibe coded project._**

I get people's disgust at at the number of vibe coded projects coming out these days. They're coming from people who dont have experience and knowledge to know what they are doing, and yet they are promising the world.  **I get it, I too am frustrated by this.**  However not every new project you see has beem vibecoded. 

[For context, I wrote this article advising against people using AI with ZFS, so it'd be idiotic for me to vibecode an entire ZFS management engine with AI.](https://klarasystems.com/articles/why-you-cant-trust-ai-to-tune-zfs/)

The core of the application was developed over several years, by myself as a hobby project.
As a former iXsystems employee, I have seen inside the sausage factory of TrueNAS as the saying goes. I wanted to design something different. I started this in the winter of 2022 once I left iXsystems. 

If you dig into the code you will no doubt find a lot of issues and ineffeciencies. (If you find them, please file a bug report so I can fix them). The project has evolved a lot over the years I worked on this.

Where AI was used (and has alwyas been disclosed at the bottom of this readme), was to improve the CSS and implement JS for modal confirmations in UI (see the v0.2 and v0.3 ./screenshots to see the old gnarly UI). As a result it used tailwind because that's the most common thing that it knows, and its easy for AI to implement.  I do plan on replacing that in time, once I find a JS/CSS dev I can hire, becuase I'm not a UI dev.  I also used claude to add some documentation since I was going to be posting this publicly and other people would not have the mental context I have for the project. 

As for my providence with ZFS and as a developer...

- I worked at iXsystems on TrueCommand and TrueNAS for 5 years.
- I have been the producer of BSD Now for over a decade.
- I currently work at Klara Systems as a ZFS Solutions Engineer alongside Allan Jude.
  - (Note: This project is unrelated to my work at KlaraSystems, I started working on this before I started working for Klara)
- I am the current developer and release maintainer for the Lumina Desktop.
- I am a release mainainer for five Fedora Releases.
  - (Fedora Security Lab, Fedora Jam, Fedora Astonomy, Fedora Games Lab, and Fedora Scientific Lab)
- I was a Puppylinux developer, and I also worked on PC-BSD, TrueOS, and Project Trident.

To address some points brought up by people on reddit in a thread someone posted about this:

- The public copyright date is set to 2025 (and not 2022), because that is when I released it publicly. 
- Yes I flattened this repo before I pushed it to github. This is common for me because I work in a private gitea where I commit eveything becuase its "private". I push a clean repo to github. [Read more about this here.](https://www.reddit.com/r/zfs/comments/1rt4eoc/comment/oafnkce/)
- [Former iX employee who I have worked with on many projects openly confirmed I gave him a demo of this in early 2024.](https://www.reddit.com/r/zfs/comments/1rt4eoc/comment/oafss9g/)
- [Another developer I've worked with before also came forward to acknowledge that I gave him a demo of this years ago.](https://www.reddit.com/r/zfs/comments/1rt4eoc/comment/oaitltr/)

Ok... now back to your regularly scheduled README.md...

***

## Features

- **ZFS Pool Management**: Create, import, export, scrub, and monitor ZFS pools
- **Dataset Management**: Create, rename, mount/unmount datasets and volumes
- **Snapshot Management**: Create, destroy, rollback, clone, and diff snapshots
- **Replication Management**: Native ZFS send/receive and Sanoid/Syncoid integration
- **Performance Monitoring**: Real-time pool I/O stats, ARC statistics, and ZFS processes
- **System Observability**: Pool history, events, kernel logs, and module parameters
- **SMART Monitoring**: Disk health, attributes, test scheduling, and error logs
- **Modern UI**: Built with Tailwind CSS and HTMX, with a Doubao-designed light theme, responsive wide-screen layout, and minimal JavaScript
- **User Management**: Relies on PAM to interact with existing local *nix user accounts on the system

## Platform Support

- **Linux**: Any distribution with OpenZFS support
- **FreeBSD**: FreeBSD 13.x and later with OpenZFS
- **NetBSD**: NetBSD 10.1 and 11.0 (amd64) with OpenZFS

The application automatically detects the operating system and adapts its behavior accordingly.

## Quick Start

### Prerequisites

- Linux or FreeBSD or NetBSD with ZFS installed
- Python 3.12+
- Node.js v20+ and npm
- sudo (required on Linux; the service runs as an unprivileged user and uses sudo for approved commands)
- ZFS utilities (zpool, zfs, zdb, etc)
- smartmontools (smartctl)
- smartd (optional but strongly recommended)
- sanoid (optional but strongly recommended)
- rsync

#### FreeBSD Package Requirements: (Automatically installed with the install script)
#### ArchLinux Requirements:
#### RHEL Package Requirements:
#### Fedora Package Requirements: 
#### SUSE Package Requirements:
#### Debain/Ubuntu/Proxmox Package Requirements: sudo nodejs npm libsodium-dev python3.13-venv python3-pip python3-full sanoid smartmontools

### Installation

**Linux:**
```bash
git clone https://github.com/webzfs/webzfs.git
cd webzfs
chmod +x install_linux.sh
sudo ./install_linux.sh
```

The installation script automatically:
- Creates a dedicated `webzfs` system user
- Installs the application to `/opt/webzfs`
- Installs all dependencies and builds assets
- Configures sudo permissions

**FreeBSD:**
```bash
git clone https://github.com/webzfs/webzfs.git
cd webzfs
chmod +x install_freebsd.sh
sudo ./install_freebsd.sh
```

The installation script automatically:
- Detects FreeBSD version (14.x or 15.x)
- Downloads pre-compiled wheels from GitHub (no Rust compilation needed)
- Installs required packages via pkg
- Installs the application to `/opt/webzfs`
- Installs all dependencies and builds assets
- Creates an rc.d service script


### Running

#### System Managed

On Linux:
```bash
sudo systemctl enable --now webzfs
```

On FreeBSD:
```bash
Sudo service webzfs start
```


#### Manually (for dev usage)

On Linux:
```bash
# Start the application
sudo -u webzfs /opt/webzfs/run.sh

# Or for development mode
sudo -u webzfs /opt/webzfs/run_dev.sh
```

On FreeBSD the application must be run as root to avoid issues with PAM:
```bash
# Start the application
/opt/webzfs/run.sh

# Or for development mode
/opt/webzfs/run_dev.sh
```


### Access

Open your browser to: **http://localhost:26619**

**Port 26619?** Z(26) + F(6) + S(19) = ZFS!

**Remote Access:** Use SSH port forwarding for security:
```bash
ssh -L 127.0.0.1:26619:127.0.0.1:26619 user@server
```

## Documentation

- **[BUILD_AND_RUN.md](BUILD_AND_RUN.md)** - Complete installation, configuration, and troubleshooting guide
- **[add_feature_demo/README.md](add_feature_demo/README.md)** - Guide for adding new features

## Configuration

Configuration is stored in `/opt/webzfs/.env`. Key settings:

- `SECRET_KEY` - Change this in production!
- `HOST` - Default: 127.0.0.1 (localhost only)
- `PORT` - Default: 26619

See [BUILD_AND_RUN.md](BUILD_AND_RUN.md) for detailed configuration options.

## Security Considerations

- Runs as dedicated `webzfs` system user with limited sudo permissions (on Linux)
- Binds to 127.0.0.1 by default (localhost only)
- Use SSH port forwarding for remote access
- Change `SECRET_KEY` in production
- Consider running behind a reverse proxy with SSL/TLS

## Development

### Local Development (No Installation Required)

If you want to develop directly from your git clone without installing to `/opt/webzfs`:

```bash
# Clone the repository
git clone https://github.com/webzfs/webzfs.git
cd webzfs

# Run the setup script (only needed once)
chmod +x setup_dev.sh
./setup_dev.sh

# Start the development server
./run_dev.sh
```

The `setup_dev.sh` script will:
- Create a Python virtual environment (`.venv`)
- Install all Python dependencies
- Install Node.js dependencies
- Build static CSS assets
- Create a `.env` configuration file with a secure SECRET_KEY

You can then make changes, commit, and push directly from this directory.

### Development from /opt/webzfs Installation

If you've installed to `/opt/webzfs`:

```bash
cd /opt/webzfs
source .venv/bin/activate
./run_dev.sh
```

### Adding New Features

For adding new features, see [add_feature_demo/README.md](add_feature_demo/README.md).

## Contributing

Contributions are welcome! Please submit issues or pull requests.

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Related Projects

- [OpenZFS](https://openzfs.org/) - Open source ZFS implementation
- [Sanoid](https://github.com/jimsalterjrs/sanoid) - Snapshot management and replication
- [SMART tools](https://www.smartmontools.org/) - Disk health monitoring

## Support

- **GitHub**: [https://github.com/q5sys/webzfs](https://github.com/webzfs/webzfs/issues)

---

## AI Usage Disclosure

- AI was used to help add comments to the source files as well as to help clean up the build and installation documentation. 
- AI was used to implement Tailwind.CSS which massively improved my previously hideous CSS. (seriously it was eyebleedingly bad, tailwind is much much better) 
- AI was used to help implement the modal JS confirmation dialogs for certain operations, because my prior attempts were rather buggy and needed to be cleaned up. 
- [Ballistic-CodeLlama-34B](https://huggingface.co/BallisticAI/Ballistic-CodeLlama-34B-v1)

## Dev Comments

I started working on this in my spare time in the Winter of 2022.  It's been slow progress, but something I've been slowly building out since then.  It's gone through a few iterations and refactoring but it's to the point where I'm happy with where it's at for my needs.

My primary focus was to design a transparent UI that interfaces with the system and doesn't rely on its own database, data collection tooling, or custom tooling to interact with the OS. While not the best for everyone, what I wanted was something that's just a UI front end to the tooling I normally would interact with on the CLI.  So I decided to use an ASGI python server and build out the code to use and run the same tooling I would as a sysadmin. These tools already exist and work, so I dont see any reason for me to try to re-invent the wheel.

FYI: You cannot delete pools or datasets with the UI, you will need to do that at the CLI. That was an intentional design choice.
