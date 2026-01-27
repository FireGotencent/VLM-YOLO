"""
开题报告 Markdown 转 Word 导出脚本
功能：将 开题报告.md 转换为格式化的 Word 文档
依赖：python-docx
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_chinese_font(run, font_name='宋体', size=12):
    """设置中文字体"""
    run.font.name = font_name
    run.font.size = Pt(size)
    # 设置中文字体
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), font_name)
    rPr.insert(0, rFonts)


def add_heading_with_style(doc, text, level):
    """添加带样式的标题"""
    heading = doc.add_heading(level=level)
    run = heading.add_run(text)
    
    # 根据级别设置字体大小
    font_sizes = {0: 22, 1: 18, 2: 16, 3: 14, 4: 12}
    size = font_sizes.get(level, 12)
    set_chinese_font(run, '黑体', size)
    run.bold = True
    
    return heading


def add_paragraph_with_style(doc, text, first_line_indent=True, font_size=12):
    """添加带样式的段落"""
    para = doc.add_paragraph()
    run = para.add_run(text)
    set_chinese_font(run, '宋体', font_size)
    
    # 首行缩进
    if first_line_indent:
        para.paragraph_format.first_line_indent = Cm(0.74)  # 约2字符
    
    para.paragraph_format.line_spacing = 1.5
    return para


def add_bold_text(para, text, font_size=12):
    """在段落中添加加粗文本"""
    run = para.add_run(text)
    run.bold = True
    set_chinese_font(run, '宋体', font_size)
    return run


def add_normal_text(para, text, font_size=12):
    """在段落中添加普通文本"""
    run = para.add_run(text)
    set_chinese_font(run, '宋体', font_size)
    return run


def parse_markdown_table(table_lines):
    """解析Markdown表格"""
    rows = []
    for line in table_lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            # 跳过分隔行
            if '---' in line or '---|' in line:
                continue
            cells = [cell.strip() for cell in line[1:-1].split('|')]
            rows.append(cells)
    return rows


def add_table_to_doc(doc, rows):
    """添加表格到文档"""
    if not rows:
        return
    
    num_cols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=num_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    for i, row_data in enumerate(rows):
        row = table.rows[i]
        for j, cell_text in enumerate(row_data):
            cell = row.cells[j]
            para = cell.paragraphs[0]
            run = para.add_run(cell_text)
            set_chinese_font(run, '宋体', 10)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # 表头加粗
            if i == 0:
                run.bold = True
    
    doc.add_paragraph()  # 表格后空行


def add_code_block(doc, code_text):
    """添加代码块（使用等宽字体）"""
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Cm(0.5)
    
    for line in code_text.split('\n'):
        run = para.add_run(line + '\n')
        run.font.name = 'Consolas'
        run.font.size = Pt(9)


def parse_and_convert(md_content, doc):
    """解析Markdown并转换为Word"""
    lines = md_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].rstrip('\r')
        
        # 跳过空行
        if not line.strip():
            i += 1
            continue
        
        # 跳过分隔线
        if line.strip() == '---':
            doc.add_paragraph()
            i += 1
            continue
        
        # 处理标题
        if line.startswith('#'):
            match = re.match(r'^(#+)\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title_text = match.group(2)
                # 主标题居中
                if level == 1:
                    heading = add_heading_with_style(doc, title_text, 0)
                    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif level == 2:
                    add_heading_with_style(doc, title_text, 1)
                elif level == 3:
                    add_heading_with_style(doc, title_text, 2)
                elif level == 4:
                    add_heading_with_style(doc, title_text, 3)
                else:
                    add_heading_with_style(doc, title_text, 4)
            i += 1
            continue
        
        # 处理代码块
        if line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i].rstrip('\r'))
                i += 1
            add_code_block(doc, '\n'.join(code_lines))
            i += 1
            continue
        
        # 处理表格
        if line.strip().startswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].rstrip('\r'))
                i += 1
            rows = parse_markdown_table(table_lines)
            add_table_to_doc(doc, rows)
            continue
        
        # 处理列表项
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            text = line.strip()[2:]
            # 处理加粗文本
            para = doc.add_paragraph(style='List Bullet')
            process_inline_formatting(para, text)
            i += 1
            continue
        
        # 处理数字列表
        if re.match(r'^\d+\.\s+', line.strip()):
            text = re.sub(r'^\d+\.\s+', '', line.strip())
            para = doc.add_paragraph(style='List Number')
            process_inline_formatting(para, text)
            i += 1
            continue
        
        # 处理加粗标题行（如 **（1）理论意义**）
        if line.strip().startswith('**') and line.strip().endswith('**'):
            text = line.strip()[2:-2]
            para = doc.add_paragraph()
            para.paragraph_format.first_line_indent = Cm(0.74)
            add_bold_text(para, text)
            i += 1
            continue
        
        # 普通段落
        para = doc.add_paragraph()
        para.paragraph_format.first_line_indent = Cm(0.74)
        para.paragraph_format.line_spacing = 1.5
        process_inline_formatting(para, line.strip())
        i += 1


def process_inline_formatting(para, text):
    """处理行内格式（加粗、斜体等）"""
    # 匹配加粗文本 **text**
    pattern = r'\*\*(.+?)\*\*'
    parts = re.split(pattern, text)
    
    is_bold = False
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # 普通文本
            if part:
                add_normal_text(para, part)
        else:
            # 加粗文本
            add_bold_text(para, part)


def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    
    # 读取Markdown文件
    md_file = script_dir / '开题报告.md'
    if not md_file.exists():
        print(f"错误：找不到文件 {md_file}")
        return
    
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 创建Word文档
    doc = Document()
    
    # 设置页面边距
    sections = doc.sections
    for section in sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)
    
    # 解析并转换
    parse_and_convert(md_content, doc)
    
    # 保存文档
    output_file = script_dir / '开题报告.docx'
    doc.save(str(output_file))
    print(f"✅ 导出成功！文件已保存至: {output_file}")


if __name__ == '__main__':
    main()
