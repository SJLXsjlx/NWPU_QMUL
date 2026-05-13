import pypandoc
import os

# ==================== 配置区 ====================
md_file = r"xxx.md" #MD文件位置
output_docx = r"xxx.docx" #导出的word位置

# 如果不想用外部文件，也可以直接把 MD 内容粘贴在这里（你现在的写法）
use_external_md = True
# ===============================================

if use_external_md:
    if not os.path.exists(md_file):
        print(f"❌ 错误：找不到 MD 文件 {md_file}")
        print("请先把 Markdown 内容保存为 pin_analysis.md")
        exit(1)
    print(f"正在读取 Markdown 文件：{md_file}")
    output = pypandoc.convert_file(
        md_file,
        to="docx",
        outputfile=output_docx,
        # extra_args=["--reference-doc=template.docx"]  # 需要模板时再取消注释
    )
else:
    # 你原来的硬编码方式（也可以继续用）
    md_text = """# 这里放你原来的整个 Markdown 内容（太长就不重复贴了）"""
    output = pypandoc.convert_text(
        md_text,
        to="docx",
        format="md",
        outputfile=output_docx,
        # extra_args=["--reference-doc=template.docx"]
    )

print(f"🎉 转换成功！")
print(f"Word 文档已生成：{output_docx}")
print(f"文件路径：{os.path.abspath(output_docx)}")