import json
import os
from html import escape
from typing import Any, Dict, List

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    _HAS_REPORTLAB = True
except Exception:
    _HAS_REPORTLAB = False


def _clean_content(content: str) -> str:
    lines = content.splitlines()
    cleaned_lines = [line.rstrip() for line in lines]
    return "\n".join(cleaned_lines).strip()


def write_text(file_path: str, content: str, mode: str = "w", encoding: str = "utf-8") -> bool:
    try:
        cleaned = _clean_content(content)
        if not cleaned:
            return False

        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, mode, encoding=encoding) as file:
            file.write(cleaned + "\n")
        return True
    except Exception:
        return False


def write_html(file_path: str, html_content: str, encoding: str = "utf-8") -> bool:
    try:
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(html_content)
        return True
    except Exception:
        return False


def write_json(file_path: str, data: Any, encoding: str = "utf-8") -> bool:
    try:
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, "w", encoding=encoding) as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def write_to_txt(file_path, content, mode="w", encoding="utf-8"):
    return write_text(file_path=file_path, content=content, mode=mode, encoding=encoding)


def _style_block() -> str:
    return """
<style>
  :root {
    --bg1: #f4f7ff;
    --bg2: #eef7f2;
    --card: #ffffff;
    --text: #1e293b;
    --muted: #64748b;
    --ok: #16a34a;
    --warn: #f59e0b;
    --err: #dc2626;
    --primary: #2563eb;
    --line: #e2e8f0;
  }
  body {
    margin: 0;
    font-family: "SF Pro Text","PingFang SC","Microsoft YaHei",sans-serif;
    color: var(--text);
    background: radial-gradient(circle at 20% -10%, #dbeafe 0%, transparent 45%),
                radial-gradient(circle at 100% 0%, #dcfce7 0%, transparent 40%),
                linear-gradient(135deg, var(--bg1), var(--bg2));
  }
  .wrap { max-width: 1040px; margin: 24px auto; padding: 0 16px 30px; }
  .hero {
    background: linear-gradient(135deg, #0f172a, #1e3a8a);
    color: #fff; border-radius: 18px; padding: 24px 28px;
    box-shadow: 0 14px 40px rgba(15, 23, 42, .25);
  }
  .hero h1 { margin: 0; font-size: 28px; font-weight: 700; }
  .hero p { margin: 8px 0 0; color: #cbd5e1; font-size: 14px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 14px 0 18px; }
  .card { background: var(--card); border-radius: 14px; padding: 14px; border: 1px solid var(--line); box-shadow: 0 8px 24px rgba(15,23,42,.06); }
  .k { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .v { font-size: 18px; font-weight: 700; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .ok { background: #dcfce7; color: #166534; }
  .warn { background: #fef3c7; color: #92400e; }
  .err { background: #fee2e2; color: #991b1b; }
  .sec { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; margin-top: 12px; box-shadow: 0 8px 24px rgba(15,23,42,.05); }
  .sec h2 { margin: 0 0 12px; font-size: 18px; color: #0f172a; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: #334155; font-weight: 700; background: #f8fafc; }
  code { background: #f1f5f9; padding: 2px 6px; border-radius: 6px; font-family: "Menlo","Consolas",monospace; font-size: 12px; }
  ul { margin: 8px 0; padding-left: 18px; }
  .muted { color: var(--muted); font-size: 12px; }
</style>
"""


def _status_badge(status: str) -> str:
    text = escape(status or "-")
    upper = (status or "").upper()
    if upper == "SUCCESS":
        return f'<span class="badge ok">{text}</span>'
    if upper.startswith("SKIPPED"):
        return f'<span class="badge warn">{text}</span>'
    return f'<span class="badge err">{text}</span>'


def build_device_report_html(result: Dict[str, Any]) -> str:
    command_rows: List[str] = []
    for item in result.get("command_results", []):
        status = "SUCCESS" if item.get("success") else "FAILED"
        command_rows.append(
            "<tr>"
            f"<td><code>{escape(str(item.get('command', '-')))}</code></td>"
            f"<td>{_status_badge(status)}</td>"
            f"<td><code>{escape(str(item.get('file_path', '-')))}</code></td>"
            "</tr>"
        )
    command_table = "\n".join(command_rows) if command_rows else "<tr><td colspan='3'>无命令执行结果</td></tr>"

    ai = result.get("ai_analysis") or {}
    suggestions = ai.get("suggestions") or []
    suggestion_html = "".join(f"<li>{escape(str(s))}</li>" for s in suggestions) or "<li>无</li>"

    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>设备巡检报告</title>"
        f"{_style_block()}</head><body><div class='wrap'>"
        "<div class='hero'>"
        f"<h1>设备巡检报告 · {escape(str(result.get('ip', '-')))}</h1>"
        f"<p>生成时间：{escape(str(result.get('run_id', '-')))} | 协议：{escape(str(result.get('protocol', '-')))}</p>"
        "</div>"
        "<div class='cards'>"
        f"<div class='card'><div class='k'>设备IP</div><div class='v'>{escape(str(result.get('ip', '-')))}</div></div>"
        f"<div class='card'><div class='k'>巡检状态</div><div class='v'>{_status_badge(str(result.get('status', '-')))}</div></div>"
        f"<div class='card'><div class='k'>厂商</div><div class='v'>{escape(str(result.get('manuf', '-')))}</div></div>"
        f"<div class='card'><div class='k'>AI平台</div><div class='v'>{escape(str(ai.get('provider', '-')))}</div></div>"
        "</div>"
        "<div class='sec'><h2>命令执行明细</h2><table><thead><tr><th>命令</th><th>状态</th><th>回显文件</th></tr></thead>"
        f"<tbody>{command_table}</tbody></table></div>"
        "<div class='sec'><h2>AI 分析结论</h2>"
        f"<p><b>结论：</b>{escape(str(ai.get('conclusion', '-')))}</p>"
        f"<p><b>风险等级：</b>{escape(str(ai.get('risk_level', '-')))}</p>"
        f"<p><b>分析：</b>{escape(str(ai.get('analysis', '-')))}</p>"
        f"<p><b>建议：</b></p><ul>{suggestion_html}</ul>"
        f"<p class='muted'>原始响应：{escape(str(ai.get('raw_response', '-'))[:600])}</p>"
        "</div></div></body></html>"
    )


def build_run_summary_html(run_id: str, results: List[Dict[str, Any]]) -> str:
    success = len([r for r in results if r.get("status") == "SUCCESS"])
    failed = len([r for r in results if r.get("status") == "CONNECTION_FAILED"])
    skipped = len([r for r in results if str(r.get("status", "")).startswith("SKIPPED")])

    rows: List[str] = []
    for item in results:
        ai = item.get("ai_analysis") or {}
        rows.append(
            "<tr>"
            f"<td><code>{escape(str(item.get('ip', '-')))}</code></td>"
            f"<td>{escape(str(item.get('protocol', '-')))}</td>"
            f"<td>{_status_badge(str(item.get('status', '-')))}</td>"
            f"<td>{escape(str(ai.get('conclusion', '-')))}</td>"
            "</tr>"
        )
    row_html = "\n".join(rows) if rows else "<tr><td colspan='4'>无设备数据</td></tr>"

    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>巡检汇总报告</title>"
        f"{_style_block()}</head><body><div class='wrap'>"
        "<div class='hero'>"
        f"<h1>巡检汇总报告 · {escape(run_id)}</h1>"
        "<p>自动化巡检批次级汇总，含设备状态与 AI 结论</p>"
        "</div>"
        "<div class='cards'>"
        f"<div class='card'><div class='k'>设备总数</div><div class='v'>{len(results)}</div></div>"
        f"<div class='card'><div class='k'>成功</div><div class='v' style='color:#15803d'>{success}</div></div>"
        f"<div class='card'><div class='k'>连接失败</div><div class='v' style='color:#b91c1c'>{failed}</div></div>"
        f"<div class='card'><div class='k'>跳过</div><div class='v' style='color:#a16207'>{skipped}</div></div>"
        "</div>"
        "<div class='sec'><h2>设备清单</h2>"
        "<table><thead><tr><th>IP</th><th>协议</th><th>状态</th><th>AI结论</th></tr></thead>"
        f"<tbody>{row_html}</tbody></table></div>"
        "</div></body></html>"
    )


def write_pdf_from_text(file_path: str, content: str) -> bool:
    try:
        if not _HAS_REPORTLAB:
            print("⚠️ 未安装 reportlab，已跳过 PDF 生成（可执行 pip install -r requirements.txt 安装）")
            return False

        cleaned = _clean_content(content)
        if not cleaned:
            return False

        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            base_font = "STSong-Light"
        except Exception:
            base_font = "Helvetica"

        doc = SimpleDocTemplate(file_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=30)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleCN",
            parent=styles["Title"],
            fontName=base_font,
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
        )
        h2_style = ParagraphStyle(
            "H2CN",
            parent=styles["Heading2"],
            fontName=base_font,
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=8,
            spaceAfter=6,
        )
        normal_style = ParagraphStyle(
            "BodyCN",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
        )

        story = []
        bullet_buffer: List[str] = []

        def flush_bullets() -> None:
            if not bullet_buffer:
                return
            items = [ListItem(Paragraph(escape(i), normal_style), leftIndent=8) for i in bullet_buffer]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=14))
            story.append(Spacer(1, 6))
            bullet_buffer.clear()

        for line in cleaned.splitlines():
            stripped = line.strip()
            if not stripped:
                flush_bullets()
                story.append(Spacer(1, 6))
                continue
            if stripped.startswith("# "):
                flush_bullets()
                story.append(Paragraph(escape(stripped[2:]), title_style))
                story.append(Spacer(1, 10))
                continue
            if stripped.startswith("## "):
                flush_bullets()
                story.append(Paragraph(escape(stripped[3:]), h2_style))
                continue
            if stripped.startswith("- "):
                bullet_buffer.append(stripped[2:])
                continue
            flush_bullets()
            story.append(Paragraph(escape(stripped), normal_style))

        flush_bullets()
        doc.build(story)
        return True
    except Exception:
        return False
