from docx import Document
from datetime import datetime
import re


class MarkdownToWordConverter:
    def __init__(self, template_path, reports_path, template_name):
        self.template_path = template_path
        self.reports_path = reports_path
        self.template_name = template_name
        self.report_name_suffix = "_strategic_report"

    def convert_markdown_to_word(self, company_name, markdown_content):
        # Load the template document
        print("Loading template document...")
        doc = Document(f"{self.template_path}{self.template_name}")

        # Manually parse the markdown content and add to the document
        print("Parsing markdown content...")
        self.parse_and_add_content(doc, markdown_content)

        # Replace placeholders in the template with actual values
        print("Populating template with parsed content...")
        self.replace_placeholders(doc, company_name)

        # Save the document
        output_path = f"{self.reports_path}{company_name.capitalize()}{self.report_name_suffix}.docx"
        doc.save(output_path)
        print(f"Report saved to {output_path}")

    def parse_and_add_content(self, doc, markdown_content):
        lines = markdown_content.split("\n")
        for line in lines:
            line = line.strip()
            if re.match(r"^#{1} ", line):
                self.add_heading(doc, line, level=1)
            elif re.match(r"^#{2} ", line):
                self.add_heading(doc, line, level=2)
            elif re.match(r"^#{3} ", line):
                self.add_heading(doc, line, level=3)
            elif re.match(r"^#{4} ", line):
                self.add_heading(doc, line, level=4)
            elif re.match(r"^#{5} ", line):
                self.add_heading(doc, line, level=5)
            else:
                self.add_paragraph(doc, line)

    def replace_placeholders(self, doc, company_name):
        date = datetime.now().strftime("%d/%m/%Y")
        for paragraph in doc.paragraphs:
            if "{{company_name}}" in paragraph.text:
                paragraph.text = paragraph.text.replace(
                    "{{company_name}}", company_name
                )
            if "{{date}}" in paragraph.text:
                paragraph.text = paragraph.text.replace("{{date}}", date)

        # Remove all placeholders after replacing the actual values
        for paragraph in doc.paragraphs:
            if (
                "{{section1_title}}" in paragraph.text
                or "{{section1_content}}" in paragraph.text
                or "{{section2_title}}" in paragraph.text
                or "{{section2_content}}" in paragraph.text
                or "{{section3_title}}" in paragraph.text
                or "{{section3_content}}" in paragraph.text
                or "{{section4_title}}" in paragraph.text
                or "{{section4_content}}" in paragraph.text
                or "{{section5_title}}" in paragraph.text
                or "{{section5_content}}" in paragraph.text
            ):
                p = paragraph._element
                p.getparent().remove(p)
                p._p = p._element = None

    def add_heading(self, doc, text, level):
        text = re.sub(r"^#+ ", "", text)
        doc.add_heading(text, level=level)

    def add_paragraph(self, doc, text):
        if text.strip():  # Avoid adding empty paragraphs
            doc.add_paragraph(text)


if __name__ == "__main__":
    template_path = "./Strategic Reports/"
    reports_path = "./Strategic Reports/"
    template_name = "report_template.docx"

    with open("Tesla1.md", "r") as file:
        markdown_content = file.read()

    converter = MarkdownToWordConverter(template_path, reports_path, template_name)
    converter.convert_markdown_to_word("Tesla", markdown_content)
