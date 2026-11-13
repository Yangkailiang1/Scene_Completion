"""Offline test support extracted without changing builder behavior."""

import io
import zipfile


def docs():
    return [
        {
            "source_id": "test",
            "name": "test.md",
            "channel": "test",
            "lines": [
                {
                    "number": 1,
                    "text": "| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |",
                }
            ]
            + [
                {
                    "number": n,
                    "text": f"| TEST-X-{n} | 异常这个词不代表类型 | {kind} | 服务可用 | 输入错误 | UC-X | check | reject | spec |",
                }
                for n, kind in enumerate(["异常", "正常", "可选", ""], 2)
            ],
        }
    ]


def workbook(rows, formula=False):
    from xml.sax.saxutils import escape

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="测试" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        for n, row in enumerate(rows, 1):
            xml += (
                f'<row r="{n}">'
                + "".join(
                    f'<c r="{chr(65 + c)}{n}" t="inlineStr">'
                    + ("<f>1+1</f>" if formula and n == 2 and c == 0 else "")
                    + f"<is><t>{escape(v)}</t></is></c>"
                    for c, v in enumerate(row)
                )
                + "</row>"
            )
        z.writestr("xl/worksheets/sheet1.xml", xml + "</sheetData></worksheet>")
    return stream.getvalue()


def recovered_document():
    text = """# 恢复测试用例
| 变更类型 | 用例编号 | 用例名称 | 用例描述 |
| --- | --- | --- | --- |
| 未提供 | RUC-001 | 查询资源 | 正常及异常分支 |

### RUC-001：查询资源
1. Actor：开发者
2. 前置条件：
   系统可访问。
3. 后置条件：返回结果。
5. 主成功路径：〔SC@SPEC-MAIN〕
   ① 开发者查询。
6. 扩展路径：
- EXT：exception：参数不合法〔SC@TC-INVALID〕 → 拒绝请求
- EXT：alternative_success：异常后重新查询成功〔SC@TC-RECOVER〕 → 返回结果
- EXT：undetermined：未明确的降级〔SC@TC-PENDING〕 → 处理方式待确认
"""
    return {
        "source_id": "recovered",
        "name": "recovered.md",
        "channel": "test",
        "lines": [{"number": n, "text": t} for n, t in enumerate(text.splitlines(), 1)],
    }


__all__ = ["docs", "recovered_document", "workbook"]
