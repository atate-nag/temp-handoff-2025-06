import re
from functools import wraps
import json
from dotenv import load_dotenv

load_dotenv()
from sklearn.cluster import KMeans
from openai import OpenAI
import numpy as np
import pandas as pd
from chains import condense_chain
import multiprocessing as mp
import threading
import concurrent.futures
import time

client = OpenAI()


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


def wrapper(q, fn, args, kwargs):
    print("wrapping")
    q.put(fn(*args, **kwargs))
    return True


def timeout(timeout=5):
    def timeout_outer(fn):
        @wraps(fn)
        def timeout_inner(*args, **kwargs):
            # wrapper = lambda x:
            start = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn, *args, **kwargs)
                while not future.done():
                    if time.time() - start > timeout:
                        raise Exception("timeout", f"function: {fn.__name__} failed")
                    time.sleep(0.2)
            # t = threading.Thread(target=fn, args=args, kwargs=kwargs)
            # t.start()

            # while t.is_alive():
            #     if time.time() - start > timeout:
            #         raise Exception('timeout', f'function: {fn.__name__} failed')
            #     time.sleep(.2)

            # with mp.Pool(5) as pool:
            #     res = pool.apply_async(fn, args=args, kwds=kwargs)
            #     # p = mp.Process(target=wrapper, args=(output, fn, args, kwargs))
            # p.start()

            # while not res.ready():
            #     print(res.ready())
            #     # print(res.successful())
            #     if time.time() - start > timeout:
            #         raise Exception("timeout", f"function: {fn.__name__} failed")
            #     time.sleep(0.2)
            # while p.is_alive:
            #     if time.time() - start > timeout:
            #         raise Exception('timeout', f'function: {fn.__name__} failed')
            #     time.sleep(.2)
            return future.result()

        return timeout_inner

    return timeout_outer


def unescape_string(value):
    if isinstance(value, str):
        return json.loads(f'"{value}"')  # This will unescape the string
    return value


def process_dict(d):
    for key, value in d.items():
        if isinstance(value, str):
            d[key] = unescape_string(value)
        elif isinstance(value, dict):
            d[key] = process_dict(value)
        elif isinstance(value, list):
            d[key] = [
                unescape_string(item) if isinstance(item, str) else item
                for item in value
            ]
    return d


def generate_condense_summary(df, label, context, subject):
    content = df[df["labels"] == label]
    content = dict_to_plain_text(content.to_dict())
    return invoke(
        condense_chain, {"content": content, "context": context, "subject": subject}
    )


def condense(
    data: list,
    key: str,
    context: str,
    subject: str,
    number_of_clusters=10,
    number_of_processes=5,
):
    # Partant d'une liste de dictionnaires, on extrait les embeddings de chaque dictionnaire
    # et on les regroupe en clusters
    # On cree un dataframe avec les embeddings et les labels des clusters
    print()
    X = [embed(text=node[key], model="text-embedding-3-large") for node in data]

    X = np.stack(X)
    print(f"Start computing clusters..")
    labels = KMeans(n_clusters=number_of_clusters, random_state=0).fit_predict(X)

    df = pd.DataFrame(data)
    df["labels"] = labels

    with mp.Pool(number_of_processes) as pool:
        results = [
            pool.apply_async(
                generate_condense_summary,
                args=(df, label, context, subject),
            )
            for label in list(set(labels))
        ]
        while not all([r.ready() for r in results]):
            print(
                f"Condense summary {[r.ready() for r in results].count(True)} / {len(results)} for {subject}."
            )
            # [print([r.get() for r in results if r.ready()])]
            time.sleep(5)

    return [r.get() for r in results]


@retry(number_of_retry=5)
@timeout(120)
def invoke(chain, parameters):
    return chain.invoke(parameters)
    # start = time.time()

    # p = mp.Process(target=chain.invoke, args=(parameters,))
    # p.start()

    # while p.is_alive():
    #     if time.time() - start > timeout:
    #         raise Exception("timeout", f"chain: {chain} failed")
    #     time.sleep(0.2)


@retry(number_of_retry=10)
@timeout(15)
def embed(text: str, model: str = "text-embedding-3-large", timeout=5):

    return client.embeddings.create(input=text, model=model).data[0].embedding


@timeout(4)
def wait_for_sec(t):
    print("start waiting")
    time.sleep(t)
    print("finish waiting")
    return t


if __name__ == "__main__":
    print("start waiting test")
    print(wait_for_sec(1))
    print("waited 1")
    print(embed("I am trying something"))
