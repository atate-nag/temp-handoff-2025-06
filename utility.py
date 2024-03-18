import re
def clean_text(text):
    # Replace special characters with an equivalent or remove them
    text = text.replace('\u2013', '-')
    text = text.replace('\u000b', ' ')
    # Remove new lines and extra spaces
    text = re.sub(r'\s+', ' ', text)
    return text