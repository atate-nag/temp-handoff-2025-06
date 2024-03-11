from docx2json import read_docx, to_json  # Assuming these are implemented elsewhere
import json
import fitz  # PyMuPDF
import json
import os
from pptx import Presentation
class Rdoc:
    def __init__(self, filepath, document_format, document_type, is_sensitive=False):
        self.filepath = filepath
        self.document_format = document_format
        self.document_type = document_type
        self.is_sensitive = is_sensitive      # doing nothing at present
        self.structured_data = None

    def build_structured_data(self):
        if self.structured_data is None:
            self.process_document()
        return self.structured_data

    def process_document(self):
        """Process the document based on its format."""
        self.structured_data = self.doc2json()

    def extract_text(self):
        """Extract raw text from the document."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def doc2json(self):
        """Convert document to structured JSON format."""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def print_structured_data(self):
        print(json.dumps(self.structured_data, indent=4))  # Convert Python dictionary to a JSON formatted string

    @staticmethod
    def create(filepath, document_format, document_type, is_sensitive=False):
        if document_format == 'docx' or document_format == 'doc':
            return WordDocumentHandler(filepath, document_format, document_type, is_sensitive)
        elif document_format == 'pdf':
            return PDFDocumentHandler(filepath, document_format, document_type, is_sensitive)
        elif document_format == 'pptx' or document_format == 'ppt':
            return PPTDocumentHandler(filepath, document_format, document_type, is_sensitive)
        # Add more conditions for other formats as necessary
        else:
            raise ValueError(f"Unsupported document format: {document_format}")

class WordDocumentHandler(Rdoc):
    def __init__(self, filepath, document_format, document_type, is_sensitive=False):
        super().__init__(filepath, document_format, document_type, is_sensitive)
        # Additional initialization specific to WordDocumentHandler if necessary

    def process_document(self):
        # Implementation for processing Word documents
        self.structured_data = self.doc2json()

    def doc2json(self):
        # Logic to convert Word document content to structured JSON
        root_node = read_docx(self.filepath)
        json_output = to_json(root_node)
        return json_output


class PPTDocumentHandler(Rdoc):
    def __init__(self, filepath, document_format, document_type, is_sensitive=False):
        super().__init__(filepath, document_format, document_type, is_sensitive)
        # Additional initialization specific to WordDocumentHandler if necessary

    def process_document(self):
        # Implementation for processing Word documents
        self.structured_data = self.doc2json()

    def doc2json(self):
        prs = Presentation(self.filepath)
        slides_data = []
        for slide_number, slide in enumerate(prs.slides):
            slide_content = {"slide_number": slide_number + 1, "elements": []}
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    slide_content["elements"].append({"type": "text", "content": shape.text})
                # Handle other element types (images, tables, etc.) as needed
            slides_data.append(slide_content)
        return json.dumps(slides_data, indent=4)

class PDFDocumentHandler(Rdoc):
    def __init__(self, filepath, document_format, document_type, is_sensitive=False):
        super().__init__(filepath, document_format, document_type, is_sensitive)
        # Additional initialization specific to PDFDocumentHandler if necessary

    def process_document(self):
        # Implementation for processing PDF documents
        self.structured_data = self.doc2json()

    def doc2json(self):
        doc = fitz.open(self.filepath)
        structured_data = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            structured_text = self.infer_structure(text)
            structured_data.append({
                "page": page_num + 1,
                "content": structured_text
            })
        return json.dumps(structured_data, indent=4)

    def infer_structure(self,text):
        lines = text.split('\n')
        structured_data = {"sections": []}
        current_section = {}
        current_content = []

        for line in lines:
            # Simple heuristic: Headings are all caps or followed by a newline
            if line.isupper() or len(line.split()) < 4:
                # Start a new section
                if current_section:
                    # Save previous section
                    current_section["content"] = current_content
                    structured_data["sections"].append(current_section)
                    current_content = []
                current_section = {"heading": line, "content": []}
            else:
                # Add to current section content
                current_content.append(line)

        # Don't forget to add the last section
        if current_section and current_content:
            current_section["content"] = current_content
            structured_data["sections"].append(current_section)

        return structured_data

def import_data_files(data_dir):
    # import all the files in the given directory and optionally write intermediates
    data_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    company_data = []  # company_data will be a list of json objects containing info about the company
    for i, file_name in enumerate(data_files):
        file_path = os.path.join(data_dir, file_name)  # Full path to the file
        _, file_extension = os.path.splitext(file_name)  # Extract file extension
        format = file_extension.lstrip('.')  # Remove the leading '.' from the extension
        print(f"format is {format}")
        doc = Rdoc.create(file_path, format, "data")
    return doc