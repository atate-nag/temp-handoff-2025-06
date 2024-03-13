import json
import os

import dotenv
import pytest
from core_components.src.tests.test_utils import (
    assert_test,
    measure_metric,
    metrics,
    test_metric,
)

dotenv.load_dotenv()

EVALUATE_EACH_INSIGHT = False


def remove_empty_elements(data):
    """
    Recursively removes empty elements from a nested dictionary or list.

    Args:
        data (dict or list): The input data to remove empty elements from.

    Returns:
        dict or list: The data with empty elements removed.
    """
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # Check if the value is a dictionary and has 'content' key with empty value or no 'children' key
                if (
                    "content" in value
                    and (not value["content"] or value["content"] == [])
                ) or "children" not in value:
                    continue  # Skip this key-value pair
                value = remove_empty_elements(
                    value
                )  # Recursively remove empty elements from the value
            new_dict[key] = value  # Add the updated value to the new dictionary
        return new_dict
    elif isinstance(data, list):
        # If the data is a list, recursively remove empty elements from each element in the list
        return [remove_empty_elements(element) for element in data]
    else:
        return data  # Return the data as is if it's neither a dictionary nor a list


def evaluate_insights():
    """
    Evaluate insights for structured and insight files.

    This function reads structured and insight files from a specified folder and evaluates the generated insights
    using predefined metrics and thresholds.

    Returns:
        None
    """
    folder = "intermediates"

    # Get a list of files starting with 'structured_company' in the specified folder
    files_sc = [
        f
        for f in os.listdir(folder)
        if f.split("/")[-1].startswith("structured_company")
    ]

    # Get a list of files starting with 'structured_market' in the specified folder
    files_sm = [
        f
        for f in os.listdir(folder)
        if f.split("/")[-1].startswith("structured_market")
    ]

    # Get a list of files starting with 'insight_company' in the specified folder
    files_ic = [
        f for f in os.listdir(folder) if f.split("/")[-1].startswith("insight_company")
    ]

    # Get a list of files starting with 'insight_market' in the specified folder
    files_im = [
        f for f in os.listdir(folder) if f.split("/")[-1].startswith("insight_market")
    ]

    # Get a list of files starting with 'structured_data' in the specified folder
    files_sd = [
        f for f in os.listdir(folder) if f.split("/")[-1].startswith("structured_data")
    ]

    # Sort the lists of files to get the structured and insight files in the same order
    files_sc.sort()
    files_sm.sort()
    files_ic.sort()
    files_im.sort()

    sd = []
    for file_sd in files_sd:
        # Read the structured data file
        with open(folder + "/" + file_sd, "r") as f:
            data_file = json.load(f)
            # Remove empty elements from the data file
            data_file = str(remove_empty_elements(data_file))
            # Append the modified data file to the list
            sd.append(data_file)

    # n = 2
    # files_sc, files_sm, files_ic, files_im = files_sc, files_sm, files_ic, files_im

    # Iterate over the zipped lists of structured and insight files
    for file_sc, file_sm, file_ic, file_im in zip(
        files_sc, files_sm, files_ic, files_im
    ):

        ##################

        # Iterate over the structured and insight files for company and market
        for structured_file, insight_file, type_ in [
            (file_sc, file_ic, "company"),
            (file_sm, file_im, "market"),
        ]:

            # Read the structured file
            with open(folder + "/" + structured_file, "r") as f:
                retrieval_context = str([json.load(f)])

            # Read the insight file
            with open(folder + "/" + insight_file, "r") as f:
                actual_output = json.load(f)

            # Define the metrics to evaluate or not evaluate
            metrics_ = [
                value
                for key, value in metrics.items()
                if key
                not in [
                    "GEval",
                    "ContextualPrecisionMetric",
                    "ContextualRecallMetric",
                    "RagasMetric",
                ]
            ]

            # Define the thresholds for the metrics
            thresholds = [0.5] * len(metrics_)

            input = (
                f"Generate the insights that relate to the company NAG Or Numerical Algorithms Group "
                f"with basic information contained in the context and potential insights "
            )
            context = sd

            # Iterate over the insights in the actual output
            print(f"\n number of insights: {len(actual_output)}")
            if EVALUATE_EACH_INSIGHT:
                for insight in actual_output:
                    print(f"\n Partial Output: {insight}")

                    # Evaluate each metric for the insight
                    for metric, threshold in zip(metrics_, thresholds):
                        print(f"\n Metric: {metric.__name__}")
                        print(
                            f"\n Result: {measure_metric(input, context, [retrieval_context], str(insight), metric, threshold, model='gpt-4-turbo-preview')}"
                        )

            print(f"\n Actual Output:")
            # Evaluate each metric for the actual output
            for metric, threshold in zip(metrics_, thresholds):
                print(f"\n Metric: {metric}")
                print(
                    f"\n Result: {measure_metric(input, context, [retrieval_context], str(actual_output), metric, threshold, model='gpt-4-turbo-preview')}"
                )


evaluate_insights()
