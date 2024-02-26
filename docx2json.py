from docx import Document
import json

class Node:
    def __init__(self, title=None, content=None, level=0):
        self.title = title
        self.content = [] if content is None else content
        self.children = []
        self.level = level
        self.parent = None  # Initialize parent

    def add_child(self, node):
        self.children.append(node)
        node.parent = self  # Set the parent of the newly added child node

    def add_content(self, text):
        # Only add non-empty and non-whitespace content
        if text.strip():
            self.content.append(text.strip())

    def to_dict(self):
        return {
            "title": self.title,
            "content": self.content,
            "children": [child.to_dict() for child in self.children]
        }

def get_heading_level(paragraph):
    """Extract heading level from paragraph style."""
    if paragraph.style.name.startswith('Heading'):
        return int(paragraph.style.name.split()[-1])
    return None

def read_docx(file_path):
    document = Document(file_path)
    root = Node("Document Root", level=0)
    current_node = root

    for paragraph in document.paragraphs:
        level = get_heading_level(paragraph)
        if level is not None:
            # Move up the tree to find the correct parent node for this level
            while current_node != root and current_node.level >= level:
                current_node = current_node.parent
            new_node = Node(title=paragraph.text, level=level)
            current_node.add_child(new_node)
            current_node = new_node
        else:
            current_node.add_content(paragraph.text)

    return root


def to_json(node):
    return json.dumps(node.to_dict(), indent=4, ensure_ascii=False)
