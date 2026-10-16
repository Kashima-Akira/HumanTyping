# HumanTyping：模拟打字与时序测试

HumanTyping 是一个 Python 打字模拟库，可以配合 Playwright、Selenium 和 Appium，逐字输入文本，并模拟速度变化、停顿、错字和退格纠正。

本仓库基于 [Lax3n/HumanTyping](https://github.com/Lax3n/HumanTyping) 的开源项目，保留原始历史与 MIT 许可证，增加按键时序修复及本地浏览器演示。

> 本项目用于输入模拟、软件测试与教学。输入节奏更丰富不代表与真人不可区分，也不保证通过任何网站的自动化检测。这里的测试结果来自本地测试页，并未验证 Ed 或其他网站的检测行为。

## 本版本的修改

- **按键按住时长**：Playwright 同步和异步接口新增 `key_hold_ms`，默认 50 毫秒，控制 `keydown` 到 `keyup` 的间隔，退格键也适用。
- **交换字母的时间间隔**：一次交换错误拆成两条独立时间戳记录，保留两个字母各自的输入时间，避免等待总时长后连续发出两次按键。
- **慢速演示**：正常输入演示的目标速度为每分钟 22.5 词（WPM）。
- **周期性随机暂停**：正常输入演示每输入约 10 秒，随机暂停 1–10 秒。暂停后重新开始计时；暂停时间不计入下一轮 10 秒。
- **可核对的结果**：本地页面显示实际按键事件，结束后保存 JSON 报告和截图。

随机暂停由演示脚本中的 `PeriodicPauseElement` 实现，并非所有 `HumanTyper` 调用默认都会暂停。短小的交换字母测试保留固定测试间隔，不使用周期暂停。

## 功能概览

- 根据单词难度、常见字母组合和键位距离调整输入速度。
- 模拟相邻键误按、字母交换及退格纠正。
- 模拟长文本中的速度变化和疲劳。
- 支持 QWERTY、AZERTY 键盘布局。
- 提供浏览器输入、终端演示和多次模拟统计。

语言模型主要面向英文，不包含中文拼音输入法的组词、候选词选择过程。

## 安装

需要 Python 3.10 或更新版本。以下命令适用于 macOS / Linux；请确认 `python3 --version` 满足要求。

```bash
git clone https://github.com/Kashima-Akira/HumanTyping.git
cd HumanTyping
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

`dev` 安装项包含运行测试和浏览器演示所需的依赖。如果只需要 Playwright 接口，可安装 `'.[playwright]'`。项目当前的基础依赖还包括 NumPy、Selenium 和 Appium 客户端。

```bash
python -c "from humantyping import HumanTyper; print('安装成功')"
```

## 运行本地浏览器演示

安装完成后执行：

```bash
python examples/timing_check.py --keep-open
```

演示会打开独立测试浏览器，在内存中的本地页面完成以下步骤：

1. 故意将 `ab` 输入为 `ba`，随后退格并纠正，检查两次按键的时间间隔。
2. 以 22.5 WPM 的目标速度输入示例文字，每输入约 10 秒随机暂停 1–10 秒。
3. 核对最终文本、实际按住时长和交换字母间隔，输出结果。

暂停时页面会显示暂停时长，之后自动继续。演示结束后窗口保持打开，关闭测试窗口即可结束程序。

不显示浏览器窗口时可运行：

```bash
python examples/timing_check.py --headless
```

结果保存在：

- `test-results/timing-report.json`：按键事件、暂停时长和测试摘要。
- `test-results/timing-check.png`：测试页面截图。

这些生成文件已被 Git 忽略，不会随源码提交。

### 调整演示参数

编辑 `examples/timing_check.py`：

- `HumanTyper(wpm=22.5, key_hold_ms=50)`：目标速度与按住时长。
- `PeriodicPauseElement` 中的 `10` 秒计时间隔：多久检查一次暂停。
- `random.uniform(1, 10)`：随机暂停时长范围，单位为秒。
- `sample`：演示输入的文本。

WPM 是目标参数，模型还会加入会话速度变化、纠错和停顿，因此把 WPM 减半不保证总耗时恰好翻倍。22.5 WPM 也不是每分钟 22.5 个字符。

## 在自己的 Playwright 脚本中使用

### 同步接口

下面的示例在本地创建输入框，不访问外部网站。

```python
from playwright.sync_api import sync_playwright
from humantyping import HumanTyper

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.set_content('<textarea id="editor"></textarea>')

    editor = page.locator("#editor")
    editor.click()
    HumanTyper(wpm=45, key_hold_ms=50).type_sync(editor, "Hello world!")

    print(editor.input_value())
    browser.close()
```

### 异步接口

```python
import asyncio
from playwright.async_api import async_playwright
from humantyping import HumanTyper

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.set_content('<textarea id="editor"></textarea>')
        editor = page.locator("#editor")
        await editor.click()
        await HumanTyper(wpm=45, key_hold_ms=50).type(editor, "Hello world!")
        print(await editor.input_value())
        await browser.close()

asyncio.run(main())
```

### 参数

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `wpm` | `60.0` | 目标输入速度，必须为正数 |
| `layout` | `"qwerty"` | 键盘布局，可选 `"qwerty"`、`"azerty"` |
| `key_hold_ms` | `50.0` | Playwright 按住时长，单位毫秒，必须为有限非负数 |

`key_hold_ms=0` 恢复原先不显式设置按住延迟的行为。默认 50 毫秒是便于验证的固定值，不是经过校准的真人按键模型。Selenium 和 Appium 的按住行为维持原实现，不使用这个参数。

执行层会从下一次等待中扣除上一次已设置的按住时间，避免重复增加延迟。浏览器和驱动仍会带来额外耗时；当模型间隔小于按住时长时，实际输入速度受按住时长限制。本版本不模拟多个键同时按住。

## 终端演示与统计

```bash
# 终端动画演示
python main.py "Hello world, this is a typing test." --mode demo --wpm 45

# 重复模拟并统计耗时
python main.py "Performance test" --mode montecarlo --n 1000 --wpm 80
```

终端演示不会自动向当前其他应用或网页输入，也不使用浏览器演示中的周期暂停。

## 测试

```bash
python -m pytest -q
```

当前测试覆盖 Playwright 同步/异步时序、交换字母的时间戳和纠错、Selenium 兼容接口、空文本及无效按住时长。浏览器演示另行检查页面实际收到的事件与最终文本。

## 项目结构

```text
humantyping/
  config.py          模型参数
  typer.py           输入状态和事件时间线
  keyboard.py        键盘布局与键位关系
  language.py        英文词语难度和常见字母组合
  integration.py     Playwright / Selenium / Appium 接口
  simulation.py      终端演示与多次模拟统计
examples/
  timing_check.py    慢速输入、随机暂停和浏览器事件测量
  ...                其他框架示例
tests/               自动化测试
main.py              终端命令入口
TIMING_FIXES.md       详细时序说明（英文）
```

## 许可与来源

采用 [MIT 许可证](LICENSE)。原项目：[Lax3n/HumanTyping](https://github.com/Lax3n/HumanTyping)。本仓库：[Kashima-Akira/HumanTyping](https://github.com/Kashima-Akira/HumanTyping)。
