from docxtpl import DocxTemplate
import json
from datetime import datetime
from markdown import markdown
from bs4 import BeautifulSoup

class StrategicReportGenerator:
    def __init__(self, template_path, reports_path, template_name):
        self.template_path = template_path
        self.reports_path = reports_path
        self.template_name = template_name
        self.report_name_suffix = '_strategic_report'
        self.agent_name = 'Socrates'

    def get_report(self, company_name):
        with open(f"{self.reports_path}{company_name}{self.report_name_suffix}.json", 'r') as json_file:
            report_dict = json.load(json_file)
        return report_dict

    def format_markdown(self, text):
        html = markdown(text)
        soup = BeautifulSoup(html, 'html.parser')
        formatted_text = ""

        for element in soup:
            if element.name == 'p':
                formatted_text += f"{element.get_text()}\n\n"
            elif element.name == 'ul':
                for li in element.find_all('li'):
                    formatted_text += f"• {li.get_text()}\n"
            elif element.name == 'ol':
                for idx, li in enumerate(element.find_all('li'), start=1):
                    formatted_text += f"{idx}. {li.get_text()}\n"
            elif element.name in ['h1', 'h2', 'h3']:
                formatted_text += f"\n{element.get_text().upper()}\n\n"

        return formatted_text.strip()

    def get_context(self, company_name, report_dict):
        date = datetime.now().strftime('%d/%m/%Y')
        report_context = {
            'company_name': company_name.capitalize(),
            'author': self.agent_name,
            'date': date,
            'section1_title': 'Introduction',
            'section1_content': self.format_markdown(report_dict.get('introduction', '')),
            'section2_title': 'Detailed Analysis',
            'section2_content': self.format_markdown(report_dict.get('detailed_analysis', '')),
            'section3_title': 'Prioritization',
            'section3_content': self.format_markdown(report_dict.get('prioritization', '')),
            'section4_title': 'Barriers, Risks, Challenges',
            'section4_content': self.format_markdown(report_dict.get('barriers_risks_challenges', '')),
            'section5_title': 'Executive Summary',
            'section5_content': self.format_markdown(report_dict.get('barriers_risks_challenges', '')),

        }
        return report_context

    def generate_report(self, company_name):
        template = DocxTemplate(f"{self.template_path}{self.template_name}")
        report = self.get_report(company_name)
        context = self.get_context(company_name, report)

        # Render and save the template
        template.render(context)
        template.save(f"{self.reports_path}{company_name.capitalize()}{self.report_name_suffix}.docx")


if __name__ == '__main__':
    template_path = './Strategic Reports/'
    reports_path = './Strategic Reports/'
    template_name = 'report_template.docx'

    generator = StrategicReportGenerator(template_path, reports_path, template_name)
    generator.generate_report('Berkshire_Hathaway')
