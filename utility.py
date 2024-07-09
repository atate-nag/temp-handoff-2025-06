import re
from functools import wraps


def clean_text(text):
    # Replace special characters with an equivalent or remove them
    text = text.replace("\u2013", "-")
    text = text.replace("\u000b", " ")
    # Remove new lines and extra spaces
    text = re.sub(r"\s+", " ", text)
    return text


def dict_to_plain_text(data, indent_level=0):
    """
    Transform an unstructured dictionary into plain text to make it easy for LLM to read.

    Parameters:
        data (dict): The dictionary to transform.
        indent_level (int): The current indentation level for nested dictionaries and lists.

    Returns:
        str: A string representing the dictionary in plain text.
    """
    plain_text = ""
    indent = "    " * indent_level  # 4 spaces per indent level

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                plain_text += f"{indent}{key}:\n"
                plain_text += dict_to_plain_text(value, indent_level + 1)
            elif isinstance(value, list):
                plain_text += f"{indent}{key}:\n"
                plain_text += dict_to_plain_text(value, indent_level + 1)
            else:
                plain_text += f"{indent}{key}: {value}\n\n"
        plain_text += "\n"
                
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) or isinstance(item, list):
                plain_text += dict_to_plain_text(item, indent_level + 1)
            else:
                plain_text += f"{indent}- {item}\n"
        plain_text += "\n"
    else:
        plain_text += f"{indent}{data}\n\n"

    return plain_text


def json_to_markdown(json_obj):
    markdown = ""

    for section in json_obj["TableOfContents"]:
        markdown += f"# {section['Section']}\n"
        for subsection in section["Subsections"]:
            markdown += f"## {subsection['Subsection']}\n"
            markdown += f"{subsection['content']}\n\n"
            # markdown += f"### Data needed\n"
            # markdown += f"{subsection['data_needed']}\n\n"
            markdown += f"### Statements\n"
            markdown += f"{subsection['content_statements']}\n\n"

    return markdown

def dict_to_markdown(data):
    markdown = ""
    for key, value in data.items():
        markdown += f"## {key}\n"
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                markdown += f"### {sub_key}\n"
                markdown += f"{sub_value}\n\n"
        else:
            markdown += f"{value}\n\n"
    return markdown

def retry(number_of_retry=3):
    def retry_outer(fn):
        @wraps(fn)
        def retry_inner(*args, **kwargs):
            for i in range(number_of_retry):
                try:
                    response = fn(*args, **kwargs)
                    return response
                except Exception as e:
                    print(e)
                    print(f"Retry {i+1}/{number_of_retry}")

        return retry_inner

    return retry_outer