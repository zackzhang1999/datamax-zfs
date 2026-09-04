# DataMax-zfs - ZFS Web Management Interface
本项目基于 webzfs 项目二次开发,感谢webzfs作者贡献

A modern web-based management interface for ZFS pools, datasets, snapshots, and SMART disk monitoring built with Python FastAPI and HTMX.

<img width="2786" height="2514" alt="image" src="https://github.com/user-attachments/assets/1fe5bf25-8dde-4e9c-b079-77ce1826e618" />
<img width="2454" height="1874" alt="image" src="https://github.com/user-attachments/assets/2ab4ba4c-01d1-481a-84dc-349e64761853" />
<img width="3038" height="3002" alt="image" src="https://github.com/user-attachments/assets/e1abb193-9eb0-4857-adb5-d0031ce56b97" />
<img width="2760" height="2762" alt="image" src="https://github.com/user-attachments/assets/a2632ab7-87b7-4693-988e-4a9fc9ce58b0" />





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

