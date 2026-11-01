# feedback-app

一个最小反馈收集工具：命令行提交反馈文本，存储在进程内列表中。

## 安装

无需额外依赖，Python 3.8+ 即可运行。确认本机 Python 可用：

```text
python --version
```

## 快速开始

提交一条反馈：

```text
python feedback_app.py submit "页面加载慢"
```

再提交一条：

```text
python feedback_app.py submit "按钮错位"
```

提交内容包含空格时请给参数加引号：

```text
python feedback_app.py submit "提交按钮在移动端不可见"
```

## 运行测试

测试命令以 `pyproject.toml` 中 `[tool.feedback-app]` 的 `test-command` 为准：

```text
python -m unittest discover -s tests -v
```

也可以运行单个测试模块：

```text
python -m unittest tests.test_feedback_app -v
```

## 调试

打开 Python 交互环境手动检查存储行为：

```text
python -i feedback_app.py
```

在交互环境里输入 `python` 语句验证 `FeedbackStore` 的行为：

```text
python -c "from feedback_app import FeedbackStore; s = FeedbackStore(); print(s.add('hello'))"
```

## 已知问题

- 提交成功后没有确认提示。
- 提交失败时直接崩溃，没有重试引导。
- 无法查看历史提交记录。
- 提交空内容会导致程序崩溃（traceback 退出）。

## 更多示例

带引号的中文反馈：

```text
python feedback_app.py submit "希望支持导出 CSV"
```

再次强调测试命令：

```text
python -m unittest discover -s tests
```

错误用法（缺参数）会打印 usage：

```text
python feedback_app.py
```

查看 Python 帮助：

```text
python --help
```
