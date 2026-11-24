# v1.2 · 中英双语首版 / First bilingual release

一个 Windows 小工具：**读取 Uber 历史行程 → 勾选 → 批量下载 PDF 发票 / 收据**。单文件 exe，不装 Python 也能跑。

A small Windows tool that lists your Uber trips and downloads their PDF receipts in bulk. Single exe, no Python needed.

---

## 下载哪个 / Which file

| 文件 | 说明 |
|---|---|
| `Uber发票助手_v1.2.zip` | 中文界面（默认跟随系统语言）|
| `UberInvoiceTool_v1.2.zip` | English UI |

两个包内容一致，只是界面语言和文件命名前缀不同（`Uber收据_` vs `UberReceipt_`）。

## 这次有什么

- **日历选日期**：点日期框弹出小日历，起止日期任意选
- **行程总览**：日期 / 时间 / 金额 / 地点 / 状态，点列头排序
- **单击勾选**、批量下载；超过 30 张先确认并给预计耗时
- **按币种分行统计**：SAR / AED / EGP / BHD … 分别合计（不混算），每类前面带小国旗
- **发票优先、收据兜底**：沙特取官方发票文件；阿联酋等地区取收据弹窗里的「下载 PDF」，最后才退回打印页面
- **弱网容错**：0.3–0.9 秒随机延时；限流重试 2 次、网络错误重试 4 次；连续失败自动停并说明原因
- **本地运行**：直接访问 Uber 网页接口，不经过任何第三方服务器

## 首次使用

1. 双击 exe（Windows 可能提示"已保护你的电脑"→ 更多信息 → 仍要运行）
2. 选日期 → 点「读取行程」
3. 会弹出一个**独立的浏览器窗口**（不是你日常的浏览器），在里面登录一次 Uber
4. 回到程序再点一次「读取行程」→ 勾选 → 选目录 → 下载

> ⚠ **读取和下载期间不要关掉那个浏览器窗口**，关掉会导致连接断开、下载中断（重开即可，已下载的文件不受影响）。

Session 存在 `%LOCALAPPDATA%\UberInvoiceTool\profiles\`，只有第一次需要登录。

## 环境要求

- Windows 10 / 11（64 位）
- 任一个 Chromium 内核浏览器（系统自带 Edge 就够）——Firefox、Safari 不行
- 你自己的 Uber 账号

## 已知限制

- 金额与日期来自行程列表卡片，不是从 PDF 内容反读的
- 单次读取软上限 300 条（可确认继续读更早的）
- 非沙特国家的"收据"取决于 Uber 页面是否提供「下载 PDF」入口
- exe 未做代码签名，SmartScreen 会提示

## 免责声明

个人工具，仅用于导出**自己账号**下的行程收据。请遵守 Uber 服务条款；不要用于抓取他人数据或伪造收据。

---

License: MIT
