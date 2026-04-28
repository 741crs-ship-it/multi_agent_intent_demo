"""临时脚本：从桌面需求 docx 抽出纯文本。"""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def docx_to_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    texts: list[str] = []
    for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
        if t.text:
            texts.append(t.text)
        if t.tail:
            texts.append(t.tail)
    return "".join(texts)


def main() -> None:
    paths = [
        Path(r"C:\Users\1\Desktop\财小资基础功能需求（初版.docx"),
        Path(r"C:\Users\1\Desktop\0819-财资pc首页接入ai助手财小资需求V0.2.docx"),
    ]
    out_dir = Path(__file__).resolve().parents[1] / "doc_extracted"
    out_dir.mkdir(exist_ok=True)
    for p in paths:
        txt = docx_to_text(p)
        out_path = out_dir / (p.stem + ".txt")
        out_path.write_text(txt, encoding="utf-8")
        # 避免 Windows 终端默认 GBK 导致 print 报 UnicodeEncodeError
        print("WROTE", out_path, "chars=", len(txt))


if __name__ == "__main__":
    main()
