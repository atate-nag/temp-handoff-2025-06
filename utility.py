import re


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
