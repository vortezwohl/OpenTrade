## ADDED Requirements

### Requirement: 控制台输出对不可编码字符做安全替换
efinance_cli/executor.py 的 _emit 方法 SHALL 在调用 click.echo 前对输出文本进行编码安全检查：若文本无法以当前控制台编码（如 Windows GBK）完整编码，则将不可编码字符替换为 ?，确保命令不会因单个非法字符而整体崩溃。

#### Scenario: 含特殊 Unicode 字符的输出不崩溃
- **WHEN** 命令执行结果包含 GBK 无法编码的 Unicode 字符（如 \ufffd）
- **AND** 运行环境为 Windows 中文控制台（默认 GBK 编码）
- **THEN** 控制台输出中用 ? 替换不可编码字符
- **AND** 命令正常退出（exit_code=0）

#### Scenario: 文件输出不受影响
- **WHEN** 用户使用 --output result.txt --encoding utf-8 指定写入文件
- **THEN** 文件内容使用用户指定的 UTF-8 编码完整保留，不做字符替换
