# Uber Receipt Helper · Uber 发票助手

A small Windows tool that lists your Uber trip history, lets you tick the trips you need,
and downloads their PDF receipts in bulk.

读取 Uber 历史行程 → 勾选 → 批量下载 PDF 发票 / 收据。Windows 单文件 exe，无需安装。

## 功能

- **日历选日期**：点日期框弹出小日历，起止日期任意选
- **行程总览**：日期 / 时间 / 金额 / 地点 / 状态，点列头排序
- **勾选下载**：单击勾选，批量下载；超过 30 张先确认并给预计耗时
- **币种分行统计**：SAR / AED / EGP / BHD … 分别合计（不混算），每类前面带小国旗
- **发票优先、收据兜底**：沙特有正式发票文件；阿联酋等地区若有「下载 PDF」入口就取官方收据，最后才退回打印页面
- **弱网容错**：随机延时 + 分级重试（限流 2 次 / 网络错误 4 次）+ 连续失败自动停
- **中英双语**：同一份代码，两套界面与打包

## 怎么用

1. 双击 `Uber发票助手.exe`（首次运行 Windows 可能拦一下：更多信息 → 仍要运行）
2. 选起止日期 → 点「读取行程」
3. **第一次**会弹出一个独立的浏览器窗口，在里面登录一次 Uber，回来再点一次「读取行程」
4. 表格里点「选择」列勾选 → 选目录 → 点「下载所选」

> ⚠ 读取和下载期间不要关闭那个浏览器窗口，否则连接会断、下载中断。

文件命名：`Uber收据_2026-11-22_SAR43.27.pdf`（英文版为 `UberReceipt_...`）。

## 技术路线

不打包浏览器自动化框架（否则 exe 要 300 MB 起），而是用系统浏览器自带调试协议（CDP）直连：

| 环节 | 做法 |
|---|---|
| 打开浏览器 | 用 Edge / Chrome / Brave / Vivaldi / Chromium 的 exe + 独立 `--user-data-dir`，与日常浏览器隔离 |
| 行程列表 | 列表页 URL 带 `?cursor=<base64 时间戳>`，按时间点翻页，每页约 10 条 |
| 发票 | 页面内调用站点自身的 `GetInvoiceFiles` GraphQL，拿签名下载地址后本机下载 |
| 收据兜底 | 打开行程的收据弹窗，取其中 `下载 PDF` 链接（同源 fetch），再退回 `Page.printToPDF` |
| 打包 | PyInstaller `--onefile`，最终 12.5 MB |

界面是 tkinter 自绘：位图复选框、国旗、彩色按钮图标、蓝底标题条。

## 构建

```powershell
pip install websocket-client pillow pyinstaller

# 1) 生成图标与位图素材（必须先生成，后面打包要打进 exe）
python make_icon.py
python mk_checkboxes.py
python mk_flags.py
python mk_btn_icons.py
python mk_cells.py

# 2) 打包（两个版本）
$data = @("app_icon.png","chk_off.png","chk_on.png","chk_disabled.png",
          "btn_all.png","btn_none.png","btn_clear.png",
          "flag_SAR.png","flag_AED.png","flag_QAR.png","flag_BHD.png","flag_KWD.png",
          "flag_OMR.png","flag_EGP.png","flag_USD.png","flag_GBP.png","flag_EUR.png",
          "flag_OTHER.png") | ForEach-Object { "--add-data"; "$_;." }

python -m PyInstaller --noconfirm --onefile --windowed --name "Uber发票助手" `
  --icon icon.ico --version-file version_info.txt @data --add-data "cells;cells" uber_tool.py

python -m PyInstaller --noconfirm --onefile --windowed --name "UberInvoiceTool" `
  --icon icon.ico --version-file version_info_en.txt @data --add-data "cells;cells" uber_tool_en.py
```

VS Code 里有现成配置：`.vscode/launch.json`（调试 / 演示数据）与 `.vscode/tasks.json`（生成素材、打包）。

## 数据位置

| 内容 | 路径 |
|---|---|
| 浏览器会话 | `%LOCALAPPDATA%\UberInvoiceTool\profiles\<浏览器>\` |
| 设置 | `%LOCALAPPDATA%\UberInvoiceTool\settings.json` |
| 默认下载目录 | `%USERPROFILE%\Documents\Uber发票`（英文版 `UberReceipts`）|

删除 `profiles` 目录即可清掉登录状态。

## 文件说明

| 文件 | 作用 |
|---|---|
| `uber_tool.py` | 主程序（界面 + CDP + 抓取 + i18n）|
| `uber_tool_en.py` | 英文版入口（只设置语言后调用 `main()`）|
| `make_icon.py` | 程序图标 → `icon.ico` / `app_icon.png` |
| `mk_checkboxes.py` | 三态复选框位图 |
| `mk_flags.py` | 货币国旗位图 |
| `mk_btn_icons.py` | 工具条彩色按钮图标 |
| `mk_cells.py` | 「复选框 + 国旗」合成单元格图 |
| `version_info*.txt` | exe 文件版本信息（中/英）|
| `test_*.py` | 离线自检（解析、界面、重试逻辑），不联网 |

## 已知限制

- 只支持 Windows 10/11 64 位 + Chromium 内核浏览器（自带 Edge 即可）；Firefox、Safari 不行
- 金额与日期来自行程列表卡片，不是从 PDF 反读的
- 单次读取软上限 300 条
- exe 未做代码签名，SmartScreen 会提示
- 非沙特的"收据"取决于 Uber 页面是否提供「下载 PDF」入口

## 免责声明

个人工具，仅用于导出自己在 Uber 账号下的行程收据。请遵守 Uber 服务条款；
不要用它抓取他人账号数据，也不要用于伪造收据或报销凭证。

## License

MIT
