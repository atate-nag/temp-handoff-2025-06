import json
import os
import openai
import re
from dochandler import Rdoc
from debug import dprint
from utility import dict_to_plain_text
import time


class FileHandler:
    def __init__(self, base_path="./Intermediates/"):
        self.base_path = base_path
        # self.uploaded_file_ids = {}  # Changed to a dictionary to store files by a unique key

    @staticmethod
    def extract_context(json_string, pos, context_len=100):
        """
        Extracts and returns the context around a given position in the JSON string for better error debugging.
        """
        start = max(0, pos - context_len)
        end = min(len(json_string), pos + context_len)
        return json_string[start:end]

    def split_json_objects(self, json_string):
        """
        Split a string containing multiple JSON objects into a list of JSON objects.
        This function will handle and skip over malformed JSON segments.
        """
        decoder = json.JSONDecoder()
        pos = 0
        length = len(json_string)
        json_objects = []

        while pos < length:
            try:
                match = decoder.raw_decode(json_string, pos)
                json_objects.append(match[0])
                pos = match[1]
                # Skip any whitespace between JSON objects
                while pos < length and json_string[pos].isspace():
                    pos += 1
            except json.JSONDecodeError as e:
                # Print error and skip to the next possible JSON object
                context = FileHandler.extract_context(json_string, pos)
                print(f"Skipping malformed JSON segment at position {pos}: {e}")
                print(f"Context: {context}")

                # Attempt more aggressive repair
                start_pos = pos
                while pos < length and json_string[pos] not in "{[":
                    pos += 1
                # Capture the malformed segment
                malformed_segment = json_string[start_pos:pos]
                print(f"Malformed segment: {malformed_segment}")

                # Try to skip over the malformed segment
                pos += 1

        return json_objects

    @staticmethod
    def clean_structured_data(data):
        """
        Cleans structured data to fix common issues before converting to JSON.
        """
        if isinstance(data, list):
            return [FileHandler.clean_structured_data(item) for item in data]
        elif isinstance(data, dict):
            cleaned_data = {}
            for key, value in data.items():
                cleaned_key = (
                    FileHandler.clean_json_string(key) if isinstance(key, str) else key
                )
                cleaned_value = FileHandler.clean_structured_data(value)
                cleaned_data[cleaned_key] = cleaned_value
            return cleaned_data
        elif isinstance(data, str):
            return FileHandler.clean_json_string(data)
        else:
            return data

    def process_and_save_json_files(self, path_to_dir):
        """
        Converts all non-JSON files in the specified directory to structured JSON format and saves them as JSON files.

        Parameters:
            path_to_dir (str): The path to the directory containing the files to be processed.

        Returns:
            List[str]: A list of full paths to the created JSON files.
        """
        files = os.listdir(path_to_dir)
        json_files = []

        for file_name in files:
            file_path = os.path.join(path_to_dir, file_name)
            if os.path.isfile(file_path) and not file_name.lower().endswith(".json"):
                _, file_extension = os.path.splitext(
                    file_name
                )  # Extract file extension
                file_format = file_extension.lstrip(
                    "."
                )  # Remove the leading '.' from the extension
                doc = Rdoc.create(file_path, file_format, "insight")

                # Step 2: Convert to structured format (json)
                structured_data = doc.build_structured_data()
                print(
                    f"Original structured data snippet: {json.dumps(structured_data)[:1000]}"
                )  # Debugging

                # Verify and clean the structured data
                if isinstance(structured_data, str):
                    try:
                        structured_data = json.loads(structured_data)
                    except json.JSONDecodeError as e:
                        print(f"Initial structured data is not valid JSON: {e}")

                cleaned_structured_data = self.clean_structured_data(structured_data)
                print(
                    f"Cleaned structured data snippet: {json.dumps(cleaned_structured_data)[:1000]}"
                )  # Debugging

                # Convert structured data to a JSON string
                json_string = json.dumps(cleaned_structured_data, indent=4)
                print(f"JSON string snippet: {json_string[:1000]}")  # Debugging

                # Clean and repair the JSON string
                cleaned_json_string = self.clean_json_string(json_string)
                print(
                    f"Cleaned JSON string snippet: {cleaned_json_string[:1000]}"
                )  # Debugging

                try:
                    full_info = json.loads(cleaned_json_string)
                except json.JSONDecodeError as e:
                    if "Extra data" in str(e) or "Expecting value" in str(e):
                        # Handle multiple JSON objects case
                        full_info = list(self.split_json_objects(cleaned_json_string))
                        print("Handled multiple JSON objects.")
                    else:
                        # Attempt to repair JSON if it's not just multiple JSON objects
                        repaired_json = self.attempt_to_repair_json(cleaned_json_string)
                        try:
                            full_info = json.loads(repaired_json)
                        except json.JSONDecodeError as e:
                            print(f"Failed to repair JSON: {e}")
                            continue
                # Create the JSON file path and save the JSON data
                json_file_path = os.path.splitext(file_path)[0] + ".json"
                with open(json_file_path, "w", encoding="utf-8") as json_file:
                    json.dump(full_info, json_file, indent=4)
                json_files.append(json_file_path)

        return json_files

    @staticmethod
    def write_local_file(tag, text):
        file_path = f"./Intermediates/upload{tag}.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(text.encode("utf-8"))
        return file_path

    @staticmethod
    def write_local_json(tag, data):
        # TODO - pass dictionary data not a string?
        # sdata is already a serialised json string
        file_path = f"./Intermediates/local_{tag}.json"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(data)
        return file_path

    @staticmethod
    def write_local_bin_to_json(tag, data):
        file_path = f"./Intermediates/local_{tag}.json"
        file_data_bytes = data.read()
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "wb") as file:
            file.write(file_data_bytes)
        return file_path

    @staticmethod
    def write_local_txt(tag, data):
        # TODO - pass dictionary data not a string?
        # sdata is already a serialised json string
        file_path = f"./Intermediates/local_{tag}.txt"
        # Open the file in binary mode for writing; encode the text to bytes
        with open(file_path, "w") as file:
            file.write(data)
        return file_path

    @staticmethod
    def write_local_dict(tag, data):
        # data is now a dictionary
        file_path = f"./Intermediates/local_{tag}.json"
        # Open the file in write mode
        with open(file_path, "w") as file:
            json.dump(data, file)
        return file_path

    def local_json_read(self, local_filename):
        # reads local json file and returns dictionary
        with open(f"{local_filename}", "r", encoding="utf-8") as json_file:
            json_content = json_file.read()
        # TODO store local files in class
        return json.loads(json_content)

    @staticmethod
    def clean_json_string(s):
        """
        Cleans a JSON string in common ways that JSON is often invalid.
        """
        # Fix unquoted keys (assumes keys are valid Python identifiers)
        s = re.sub(r"([{,]\s*)([a-zA-Z_]\w*)(\s*:)", r'\1"\2"\3', s)

        # Fix booleans
        s = re.sub(r"\b(True|False|null)\b", lambda m: m.group(0).lower(), s)

        # Fix escaping issues
        s = s.replace("\\'", "'")  # Single quotes should not be escaped in JSON
        s = s.replace("\\\\", "\\")  # Unescape escaped backslashes
        s = s.replace("\\/", "/")  # Unescape escaped slashes

        # Remove stray backslashes not followed by a valid escape sequence
        s = re.sub(r'\\([^"\\/bfnrtu])', r"\1", s)

        # Fix issues with trailing backslashes
        s = re.sub(r"\\$", "", s)

        # Remove newlines within strings (only the escaped newlines)
        s = re.sub(r"\\n", " ", s)
        s = re.sub(r"\\r", " ", s)

        # Remove trailing commas in objects and arrays
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*]", "]", s)

        return s.strip()

    def extract_json_from_response(self, client, thread):
        """
        Get JSON data directly from agent thread via messages
        """
        messages = client.beta.threads.messages.list(thread_id=thread.id).data
        for message in messages:
            if message.role == "assistant":  # Identify the assistant's message
                for content in message.content:
                    if content.type == "text":
                        match = re.search(r"\{.*\}", content.text.value, re.DOTALL)
                        if match:
                            json_string = match.group()
                            cleaned_json_string = self.clean_json_string(json_string)
                            try:
                                full_info = json.loads(cleaned_json_string)
                                dprint(f"JSON found in the message, returning it")
                                return full_info
                            except json.JSONDecodeError as e:
                                dprint(f"Failed to decode JSON: {e}")
                                dprint(
                                    f"Faulty JSON string: {repr(cleaned_json_string)}"
                                )
                                repaired_json = (
                                    "["
                                    + re.sub(
                                        r"\}\s*,\s*\{",
                                        "}, {",
                                        cleaned_json_string.strip(),
                                    )
                                    + "]"
                                )
                                try:
                                    # Load the repaired JSON string
                                    full_info = json.loads(repaired_json)
                                    dprint("Repaired JSON loaded successfully")
                                    return full_info
                                except json.JSONDecodeError as e:
                                    print(f"Failed to decode JSON: {e}")
                                    print(f"Faulty JSON string: {repr(repaired_json)}")
                        else:
                            dprint("No JSON found in the message, returning None")
                            return None
        # Extremely naughty AI did not produce anything! Hopefully next round will be better
        dprint("No JSON content was found")
        return None

    def extract_json_from_response_text(self, response):
        """
        Get JSON data directly from provided agent response text and return as a dictionary or list.
        Specifically looks for JSON containing "completed" key, and optionally "agent instructions" key.
        """
        # Adjusting regex to capture JSON data enclosed within markdown code blocks
        # and be resilient to the absence of newlines
        json_pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
        matches = json_pattern.findall(response)

        for json_string in matches:
            cleaned_json_string = self.clean_json_string(json_string)
            try:
                json_data = json.loads(cleaned_json_string)
                if isinstance(json_data, dict):
                    dprint("Specific JSON found in the message, returning it")
                    return json_data
            except json.JSONDecodeError as e:
                dprint(f"Failed to decode JSON: {e}")
                dprint(f"Faulty JSON string: {repr(cleaned_json_string)}")
                repaired_json = self.attempt_to_repair_json(cleaned_json_string)
                try:
                    json_data = json.loads(repaired_json)
                    if isinstance(json_data, dict) and "completed" in json_data:
                        dprint("Repaired JSON loaded successfully")
                        return json_data
                except json.JSONDecodeError as e:
                    dprint(f"Failed to decode JSON after repair: {e}")
                    dprint(f"Faulty JSON string: {repr(repaired_json)}")

        dprint("No specific JSON content found in the message")
        return None

    def attempt_to_repair_json(self, json_string):
        """
        Attempt to repair a JSON string that could not be decoded.
        This might involve fixing common JSON formatting issues.
        """
        try:
            # Try to load with trailing commas removed
            json_data = json.loads(json_string)
            return json.dumps(json_data)  # Serialize back to string to clean it
        except json.JSONDecodeError:
            pass
        repaired_json_string = self.clean_json_string(json_string)
        return repaired_json_string

# output = '**Step 0: Reproduction of Input File Contents**\n\n**Content of file (UID: 7f32bea3-7c80-4371-abaa-fca639df4a9e):**\n\n"Citigroup, a global banking institution, faces the intricate task of executing a large-scale strategic transformation amidst a challenging regulatory environment and intense market competition. With the need to simplify its operations and focus on profitable sectors, Citigroup must also address data management and cybersecurity concerns. How can Citigroup streamline its global operations to enhance customer service and shareholder value in an increasingly digital world?"\n\n---\n\n**Content of file (UID: 208ae433-ad1c-4429-89f0-53323838a30c):**\n\n[\n  "\\"The analysis identifies several key trends impacting Citigroup as it navigates its strategic transformation. These trends encompass the growth in digital payments, the adoption of new payment technologies, the shift from cash to electronic transactions, and the increasing importance of ease of use and value-added services.\\n\\n**1. Growth in Digital Payments and Financial Inclusion:**\\n- The adoption of digital payments is accelerating globally, driven significantly by regions like Latin America and the Caribbean (LAC) where financial inclusion and economic activity have surged post-COVID-19 (WEF_Accelerating_Digital_Payments_in_Latin_America_and_the_Caribbean_2022.pdf). \\n- QR code payments, cryptocurrencies, and real-time payments (RTPs) are transforming the payment landscape, necessitating the development of inclusive digital payments infrastructure for economic growth.\\n\\n**2. Shift to Electronic Transactions:**\\n- The movement towards electronic transactions has pushed merchant acquiring companies to evolve, offering value-added services beyond traditional processing (2021-mckinsey-global-payments-report.pdf). \\n- SMEs are rapidly adopting these technologies, indicating a significant opportunity in the digitization of small-business commerce (2021-mckinsey-global-payments-report.pdf).\\n\\n**3. Transformation of Merchant Services:**\\n- Acquirers are increasingly transforming into marketplaces, offering comprehensive solutions like payments disbursement, financing, and onboarding for SMEs, as well as SME-facing risk and identity solutions (2020-mckinsey-global-payments-report-vf.pdf).\\n- The consolidation in the merchant acquiring industry and the shift towards platform businesses for larger merchants highlight the trend towards integrated and industry-specific solutions (2020-mckinsey-global-payments-report-vf.pdf).\\n\\n**4. Rise of Alternative Payment Methods (APMs) and Mobile Commerce:**\\n- Alternative Payment Methods (APMs), such as e-wallets and instant-payment solutions, are crucial in accelerating the move away from cash, especially in developing economies (Financial_Services_Application_Market.pdf).\\n- Mobile commerce is on the rise, with significant increases in mobile cellular and smartphone subscriptions leading to a surge in mobile-based digital payments in regions like LAC and ASEAN (WEF_Accelerating_Digital_Payments_in_Latin_America_and_the_Caribbean_2022.pdf; WEF_Shaping the_Future_of_Cross-Border_Fast_Payment_Systems_2023.pdf).\\n\\n**5. Integration and Modernization of Payment Systems:**\\n- The rapid adoption of real-time payment systems (RTP) in countries such as Brazil demonstrates how central banks are modernizing to promote digitalization and provide common settlement infrastructures (WEF_Accelerating_Digital_Payments_in_Latin_America_and_the_Caribbean_2022.pdf; WEF_Modernizing_Financial_Markets_with_Wholesale_Central_Bank_Digital_Currency_2024.pdf).\\n- Initiatives like the linkage of Thailand’s PromptPay and Singapore’s PayNow illustrate the viability of cross-border fast payment systems, highlighting the need for seamless, efficient transactions globally (WEF_Shaping the_Future_of_Cross-Border_Fast_Payment_Systems_2023.pdf).\\n\\n**6. Increased Demand for Enhanced Payment Services:**\\n- As digital commerce grows, merchants face higher decline and fraud rates, driving demand for enhanced services that provide improved authorization rates and payment performance (2021-mckinsey-global-payments-report.pdf).\\n- Investments in digital payment solutions are expected to grow significantly, indicating a shift towards more secure and efficient transactions, including the use of digital currencies and tokenized deposits (WEF_Technology_Innovation_and_Systemic_Risk_2023.pdf).\\n\\n**7. Changes in Consumer Behavior and Business Models:**\\n- The COVID-19 pandemic has accelerated the shift to digital payments and e-commerce, compressing years of change into a short period. This rapid transformation is evident in the significant decline in cash transactions and ATM usage, with a corresponding rise in digital and contactless payments (WEF_Quantum_Readiness_Toolkit_2023.pdf; World-Retail-Banking-Report-2021.pdf).\\n- The modernization of Real-Time Gross Settlement (RTGS) systems by central banks further underscores the push towards efficient interbank payments and securities transactions (WEF_Modernizing_Financial_Markets_with_Wholesale_Central_Bank_Digital_Currency_2024.pdf).\\n\\nCitigroup can leverage these trends to streamline its global operations by investing in digital transformation, enhancing its payment services, and focusing on financial inclusion. By doing so, Citigroup can improve customer service and shareholder value in an increasingly digital world.\\n\\n**Sources:**\\n- WEF_Accelerating_Digital_Payments_in_Latin_America_and_the_Caribbean_2022.pdf\\n- WEF_Shaping the_Future_of_Cross-Border_Fast_Payment_Systems_2023.pdf\\n- 2021-mckinsey-global-payments-report.pdf\\n- 2020-mckinsey-global-payments-report-vf.pdf\\n- Financial_Services_Application_Market.pdf\\n- WEF_Modernizing_Financial_Markets_with_Wholesale_Central_Bank_Digital_Currency_2024.pdf\\""\n]\n\n---\n\n**Content of file (UID: c8865edc-f514-4ec6-838e-34791f705d18):**\n\n[\n  "\\"Citigroup is navigating a complex strategic transformation to simplify its operations and concentrate on profitable sectors while addressing data management and cybersecurity concerns. Several key trends are impacting Citigroup\'s efforts to enhance customer service and shareholder value in the digital age. Below is a summary of these influential trends:\\n\\n1. **Data Analytics and Advanced Technologies**: Citigroup must leverage advanced analytics to improve decision-making processes and optimize business operations. The increasing adoption of decision analytics, advanced analytics, and business intelligence (BI) applications will drive deeper insights, better predictions, and enhanced business outcomes (Advanced_Analytics_Market.pdf; Marketing_Analytics_Software_Market.pdf).\\n\\n2. **Cloud Solutions**: The migration to cloud platforms is pivotal for scalability, cost-efficiency, and improved service offerings. There is a noticeable shift towards cloud-first and cloud-only strategies, enabling flexibility and reducing installation and maintenance costs. Multi-cloud and hybrid-cloud solutions are also gaining traction, providing robust security measures and flexibility in deployment models (DigitalTechnologyTrends.pdf; Big_Data_Market_Sample_Report.pdf).\\n\\n3. **Managed Services**: Organizations are increasingly turning to managed service providers to focus on core business functions while outsourcing technical expertise and service consistency. This trend is evident in the growing market for managed services in advanced analytics, predictive analytics, and general IT operations (Predictive_Analytics_Market.pdf; Advanced_Analytics_Market.pdf).\\n\\n4. **Cybersecurity**: With the rise in cyberattacks driven by geopolitical conflicts and sophisticated hacking tools, enhancing cybersecurity measures is crucial. Protecting sensitive data, maintaining customer trust, and complying with regulatory requirements are paramount as the frequency and sophistication of cyber threats continue to grow (Predictive_Analytics_Market.pdf; HealthcareLifeSciences-Investment-Outlook-010424.pdf).\\n\\n5. **Customer Experience and Support**: Superior customer support and real-time analytics are becoming critical in vendor selection and improving customer service. Companies are prioritizing vendors that offer exceptional results and strong support, even at higher costs. Real-time insights and efficient onboarding processes significantly enhance customer experiences and operational efficiency (ConsumerGoodsMarketOverviewUS2023.pdf; Predictive_Analytics_Market.pdf).\\n\\n6. **Collaboration and Ecosystem Partnering**: Building partnerships within the AI ecosystem and enhancing workplace collaboration are vital for driving innovation and operational success. This approach helps leverage industry best practices, bridge capability gaps, and foster team integration, leading to effective responses and recovery activities (WEF_Harnessing_the_AI_Revolution_in_Industrial_Operations_2023.pdf; McKinsey_Global_Payments_Report.pdf).\\n\\n7. **Digitalization and Workforce Optimization**: The shift to digital platforms and workforce optimization solutions helps improve efficiency, reduce costs, and enhance employee productivity. This trend underscores the need for robust data management, cloud-based solutions, and advanced financial software to meet evolving consumer and business demands (Risk_Vendors_2018.pdf; Financial_Services_Application_Market.pdf).\\n\\nIn summary, Citigroup\'s strategic initiatives should focus on harnessing the power of data analytics, embracing cloud technologies, enhancing cybersecurity, improving customer support, fostering strategic partnerships, and optimizing workforce efficiency. These trends provide a roadmap for streamlining global operations and achieving superior customer service and shareholder value in an increasingly digital world.\\""\n]\n\n---\n\n**Step 1: Problem Statement Breakdown**\n\n**ProblemStatementBreakdown**:\n\n- **MainTask**:\n  - Streamline Citigroup\'s global operations.\n- **MainObjective**:\n  - Enhance customer service.\n  - Increase shareholder value.\n- **ConstraintsRequirements**:\n  - Operate amidst a challenging regulatory environment.\n  - Address intense market competition.\n  - Simplify operations and focus on profitable sectors.\n  - Address data management concerns.\n  - Address cybersecurity concerns.\n- **InformationContext**:\n  - Citigroup is undergoing a large-scale strategic transformation.\n  - The digital world is increasingly impacting banking operations.\n- **Definitions**:\n  - **Streamline**: Make (an organization or system) more efficient and effective by employing faster or simpler working methods.\n  - **Shareholder Value**: The return on investment that shareholders receive from owning shares in a company.\n  - **Digital Transformation**: The adoption of digital technology by an organization to improve efficiency, value, or innovation.\n- **Concepts**:\n  - Regulatory compliance.\n  - Operational efficiency.\n  - Digitalization.\n  - Customer service excellence.\n  - Cybersecurity.\n\n---\n\n**Step 2: Consideration of Scenarios**\n\nBased on the provided trends and company capabilities, we will model the following scenarios:\n\n1. **Scenario 1**: Accelerate Digital Transformation.\n2. **Scenario 2**: Divest Non-Core Business Units.\n3. **Scenario 3**: Invest Heavily in Cybersecurity Infrastructure.\n4. **Scenario 4**: Expand into Emerging Markets through Financial Inclusion Initiatives.\n\n---\n\n**Scenario 1: Accelerate Digital Transformation**\n\n**Step 3**: Estimate the Cost (C)\n\n- **Implementation of Advanced Analytics and AI**: $2 billion.\n- **Migration to Cloud Platforms**: $1.5 billion.\n- **Employee Training and Change Management**: $500 million.\n- **Total Estimated Cost (C)**: $4 billion.\n\n**Step 4**: Estimate the Opportunity Cost (O)\n\n- **Delaying other investment opportunities in profitable sectors (e.g., wealth management expansion)**: $1 billion.\n\n**Step 5**: Estimate the Potential Value Gain (V)\n\n- **Increased Operational Efficiency**: $3 billion over 5 years.\n- **Enhanced Customer Experience Leading to Increased Retention and Acquisition**: $2 billion over 5 years.\n- **Cost Savings from Workforce Optimization**: $1 billion over 5 years.\n- **Total Estimated Value Gain (V)**: $6 billion.\n\n**Step 6**: Estimate the Risk Aversion (λ)\n\n- **Risk Aversion Lambda (λ)**: 2 (Citigroup has moderate risk aversion due to regulatory pressures and past experiences).\n\n- **Risk Factors**:\n  - **Implementation Risk**: Potential delays and cost overruns, estimated at $500 million.\n  - **Cybersecurity Risk**: Increased exposure during transformation, potential losses estimated at $1 billion.\n  - **Total Estimated Risk**: $1.5 billion.\n\n**Step 7**: Calculate the Utility\n\n\\[ U(x) = V(x) - C(x) - \\lambda \\times Risk(x) \\]\n\n\\[ U = $6B - $4B - 2 \\times $1.5B = $6B - $4B - $3B = -$1B \\]\n\n---\n\n**Scenario 2: Divest Non-Core Business Units**\n\n**Step 3**: Estimate the Cost (C)\n\n- **Costs Associated with Divestiture Processes**: $1 billion.\n- **Potential Redundancy Payments and Restructuring Costs**: $500 million.\n- **Total Estimated Cost (C)**: $1.5 billion.\n\n**Step 4**: Estimate the Opportunity Cost (O)\n\n- **Loss of Future Revenue Streams from Divested Units**: $2 billion over 5 years.\n\n**Step 5**: Estimate the Potential Value Gain (V)\n\n- **Cash Inflows from Sale of Assets**: $4 billion.\n- **Improved Capital Ratios and Reduced Operational Complexity**: Leading to cost savings of $1 billion over 5 years.\n- **Total Estimated Value Gain (V)**: $5 billion.\n\n**Step 6**: Estimate the Risk Aversion (λ)\n\n- **Risk Aversion Lambda (λ)**: 1.5 (Citigroup is moderately risk-averse but sees divestiture as a way to reduce risk).\n\n- **Risk Factors**:\n  - **Market Risk**: Potential lower-than-expected sale prices due to market conditions, estimated at $500 million.\n  - **Regulatory Risk**: Complications during approval processes, estimated at $300 million.\n- **Total Estimated Risk**: $800 million.\n\n**Step 7**: Calculate the Utility\n\n\\[ U = $5B - $1.5B - 1.5 \\times $0.8B = $5B - $1.5B - $1.2B = $2.3B \\]\n\n---\n\n**Scenario 3: Invest Heavily in Cybersecurity Infrastructure**\n\n**Step 3**: Estimate the Cost (C)\n\n- **Cybersecurity Technology Upgrades**: $1 billion.\n- **Hiring Specialized Personnel**: $500 million.\n- **Employee Training Programs**: $200 million.\n- **Total Estimated Cost (C)**: $1.7 billion.\n\n**Step 4**: Estimate the Opportunity Cost (O)\n\n- **Delaying Customer-Facing Innovations**: Potential lost revenue of $500 million.\n\n**Step 5**: Estimate the Potential Value Gain (V)\n\n- **Reduced Risk of Cybersecurity Breaches**: Avoided potential losses of $2 billion.\n- **Enhanced Customer Trust Leading to Increased Business**: $500 million over 5 years.\n- **Total Estimated Value Gain (V)**: $2.5 billion.\n\n**Step 6**: Estimate the Risk Aversion (λ)\n\n- **Risk Aversion Lambda (λ)**: 3 (High risk aversion regarding cybersecurity threats).\n\n- **Risk Factors**:\n  - **Implementation Risk**: Potential integration issues, estimated at $300 million.\n- **Total Estimated Risk**: $300 million.\n\n**Step 7**: Calculate the Utility\n\n\\[ U = $2.5B - $1.7B - 3 \\times $0.3B = $2.5B - $1.7B - $0.9B = -$0.1B \\]\n\n---\n\n**Scenario 4: Expand into Emerging Markets through Financial Inclusion Initiatives**\n\n**Step 3**: Estimate the Cost (C)\n\n- **Investment in Emerging Markets Infrastructure**: $2 billion.\n- **Marketing and Local Partnerships**: $500 million.\n- **Total Estimated Cost (C)**: $2.5 billion.\n\n**Step 4**: Estimate the Opportunity Cost (O)\n\n- **Allocation of Capital Away from Developed Markets**: Potential loss of $1 billion in profits.\n\n**Step 5**: Estimate the Potential Value Gain (V)\n\n- **New Customer Acquisition**: $3 billion over 7 years.\n- **Long-term Market Positioning**: Intangible benefits estimated at $1 billion.\n- **Total Estimated Value Gain (V)**: $4 billion.\n\n**Step 6**: Estimate the Risk Aversion (λ)\n\n- **Risk Aversion Lambda (λ)**: 2.5 (Citigroup is cautious due to political and economic instability in emerging markets).\n\n- **Risk Factors**:\n  - **Country Risk**: Potential losses due to instability, estimated at $1 billion.\n- **Total Estimated Risk**: $1 billion.\n\n**Step 7**: Calculate the Utility\n\n\\[ U = $4B - $2.5B - 2.5 \\times $1B = $4B - $2.5B - $2.5B = -$1B \\]\n\n---\n\n**Step 8: JSON Output**\n\n```json\n{\n  "ProblemStatement": "Citigroup, a global banking institution, faces the intricate task of executing a large-scale strategic transformation amidst a challenging regulatory environment and intense market competition. With the need to simplify its operations and focus on profitable sectors, Citigroup must also address data management and cybersecurity concerns. How can Citigroup streamline its global operations to enhance customer service and shareholder value in an increasingly digital world?",\n  "ProblemStatementBreakdown": {\n    "MainTask": [\n      "Streamline Citigroup\'s global operations."\n    ],\n    "MainObjective": [\n      "Enhance customer service.",\n      "Increase shareholder value."\n    ],\n    "ConstraintsRequirements": [\n      "Challenging regulatory environment.",\n      "Intense market competition.",\n      "Need to simplify operations.",\n      "Focus on profitable sectors.",\n      "Address data management concerns.",\n      "Address cybersecurity concerns."\n    ],\n    "InformationContext": [\n      "Citigroup is undergoing a large-scale strategic transformation in an increasingly digital world."\n    ],\n    "Definitions": [\n      "Streamline: Make more efficient and effective by employing faster or simpler working methods.",\n      "Shareholder Value: The financial worth shareholders receive from owning shares in a company."\n    ],\n    "Concepts": [\n      "Regulatory compliance.",\n      "Operational efficiency.",\n      "Digital transformation.",\n      "Customer service excellence.",\n      "Cybersecurity."\n    ]\n  },\n  "Scenarios": [\n    {\n      "ScenarioID": "Scenario1",\n      "Description": "Accelerate Digital Transformation.",\n      "TrendsReferenced": [\n        "Growth in Digital Payments and Financial Inclusion",\n        "Shift to Electronic Transactions",\n        "Digitalization and Workforce Optimization",\n        "Data Analytics and Advanced Technologies"\n      ],\n      "Cost": 4000000000,\n      "OpportunityCost": 1000000000,\n      "ValueGain": 6000000000,\n      "Risk": 1500000000,\n      "RiskAversionLambda": 2,\n      "UtilityScore": -1000000000\n    },\n    {\n      "ScenarioID": "Scenario2",\n      "Description": "Divest Non-Core Business Units.",\n      "TrendsReferenced": [\n        "Focus on Profitable Sectors",\n        "Operational Streamlining",\n        "Capital Optimization"\n      ],\n      "Cost": 1500000000,\n      "OpportunityCost": 2000000000,\n      "ValueGain": 5000000000,\n      "Risk": 800000000,\n      "RiskAversionLambda": 1.5,\n      "UtilityScore": 2300000000\n    },\n    {\n      "ScenarioID": "Scenario3",\n      "Description": "Invest Heavily in Cybersecurity Infrastructure.",\n      "TrendsReferenced": [\n        "Cybersecurity",\n        "Data Management Concerns",\n        "Regulatory Compliance"\n      ],\n      "Cost": 1700000000,\n      "OpportunityCost": 500000000,\n      "ValueGain": 2500000000,\n      "Risk": 300000000,\n      "RiskAversionLambda": 3,\n      "UtilityScore": -100000000\n    },\n    {\n      "ScenarioID": "Scenario4",\n      "Description": "Expand into Emerging Markets through Financial Inclusion Initiatives.",\n      "TrendsReferenced": [\n        "Growth in Digital Payments and Financial Inclusion",\n        "Expansion into Emerging Markets",\n        "Customer Experience and Support"\n      ],\n      "Cost": 2500000000,\n      "OpportunityCost": 1000000000,\n      "ValueGain": 4000000000,\n      "Risk": 1000000000,\n      "RiskAversionLambda": 2.5,\n      "UtilityScore": -1000000000\n    }\n  ],\n  "UtilityAssessment": {\n    "ParameterRequirements": [\n      "Cost estimates per scenario.",\n      "Opportunity cost estimates per scenario.",\n      "Value gain estimates per scenario.",\n      "Risk assessments per scenario.",\n      "Risk aversion coefficients.",\n      "Utility scores calculated."\n    ],\n    "RequestedBy": "Strategic Scenario Evaluator"\n  },\n  "Prioritization": "Based on the utility scores calculated, Scenario 2: \'Divest Non-Core Business Units\' has the highest utility score of $2.3 billion and thus should be prioritized.",\n  "Analysis": "In analyzing the scenarios, we calculated the utility scores using the formula U(x) = V(x) - C(x) - λ × Risk(x). Scenario 2 yields the highest positive utility, primarily due to immediate cash inflows from asset sales and reduced operational complexity, which outweigh the costs and risks associated with divestiture. The other scenarios, while offering significant value gains, carry higher risks or costs that result in negative utility scores. Citigroup\'s moderate risk aversion and the regulatory environment make Scenario 2 the most viable option to streamline operations, enhance customer service indirectly through a more focused business model, and improve shareholder value by increasing profitability and efficiency."\n}\n\n```\n\n---\n\n**Prioritization**\n\nBased on the calculated utility scores, **Scenario 2: Divest Non-Core Business Units** should be prioritized as it has the highest utility score of $2.3 billion. This scenario aligns with Citigroup\'s need to simplify operations and focus on profitable sectors.\n\n---\n\n**Analysis**\n\n**Detailed Reasoning and Calculations**\n\n**Scenario 1 Analysis**\n\n- **Cost Estimation (C)**:\n  - The cost includes implementing advanced analytics and AI ($2B), migrating to cloud platforms ($1.5B), and employee training ($0.5B).\n  - These estimates are based on typical industry costs for large-scale digital transformations in global banks.\n- **Opportunity Cost (O)**:\n  - Diverting funds from other investment opportunities, such as expanding wealth management services, may result in foregone profits estimated at $1B.\n- **Value Gain (V)**:\n  - Increased operational efficiency and enhanced customer experience are expected to generate additional revenue and cost savings totaling $6B over five years.\n  - Estimates are derived from industry benchmarks where digital transformation leads to a 10-15% increase in profitability.\n- **Risk Assessment**:\n  - Implementation risks include potential project delays and cost overruns ($0.5B).\n  - Cybersecurity risks may increase during the transition period ($1B).\n- **Risk Aversion (λ)**:\n  - Citigroup\'s moderate risk aversion (λ=2) reflects its cautious approach due to regulatory pressures.\n- **Utility Calculation**:\n  - U = $6B - $4B - 2 × $1.5B = -$1B\n  - Negative utility indicates the risks and costs outweigh the benefits in this scenario.\n\n**Scenario 2 Analysis**\n\n- **Cost Estimation (C)**:\n  - Costs include legal fees, advisory services, and restructuring costs totaling $1.5B.\n- **Opportunity Cost (O)**:\n  - Loss of future revenues from divested units estimated at $2B over five years.\n- **Value Gain (V)**:\n  - Immediate cash inflows from sales ($4B).\n  - Improved capital ratios and reduced operational complexity leading to cost savings ($1B).\n- **Risk Assessment**:\n  - Market risk due to potential lower sale prices ($0.5B).\n  - Regulatory risk in obtaining approvals ($0.3B).\n- **Risk Aversion (λ)**:\n  - Slightly lower risk aversion (λ=1.5) as divestiture reduces overall organizational risk.\n- **Utility Calculation**:\n  - U = $5B - $1.5B - 1.5 × $0.8B = $2.3B\n  - Positive utility suggests that benefits significantly outweigh the costs and risks.\n\n**Scenario 3 Analysis**\n\n- **Cost Estimation (C)**:\n  - Upgrading cybersecurity infrastructure and personnel costs amount to $1.7B.\n- **Opportunity Cost (O)**:\n  - Potential delays in customer-facing innovations, leading to a $0.5B opportunity cost.\n- **Value Gain (V)**:\n  - Avoided losses from potential breaches ($2B).\n  - Increased customer trust generating additional revenue ($0.5B).\n- **Risk Assessment**:\n  - Implementation risks estimated at $0.3B.\n- **Risk Aversion (λ)**:\n  - High risk aversion (λ=3) due to the severe implications of cybersecurity breaches.\n- **Utility Calculation**:\n  - U = $2.5B - $1.7B - 3 × $0.3B = -$0.1B\n  - Slightly negative utility indicates marginal benefits over costs when adjusted for risk aversion.\n\n**Scenario 4 Analysis**\n\n- **Cost Estimation (C)**:\n  - Investments in infrastructure and partnerships totaling $2.5B.\n- **Opportunity Cost (O)**:\n  - Diverted capital from developed markets results in an opportunity cost of $1B.\n- **Value Gain (V)**:\n  - Long-term gains from new customer acquisition and market positioning totaling $4B.\n- **Risk Assessment**:\n  - High country risk due to political and economic instability in emerging markets ($1B).\n- **Risk Aversion (λ)**:\n  - Higher risk aversion (λ=2.5) reflecting cautiousness in unstable markets.\n- **Utility Calculation**:\n  - U = $4B - $2.5B - 2.5 × $1B = -$1B\n  - Negative utility indicates risks and costs outweigh the expected benefits.\n\n**Conclusion**\n\n- **Scenario 2** offers the highest utility, indicating that divesting non-core business units is the most strategic option.\n- It provides immediate financial benefits, reduces organizational complexity, and aligns with the main objectives of enhancing shareholder value and streamlining operations.\n- The analysis demonstrates meticulous consideration of costs, opportunity costs, value gains, risks, and Citigroup\'s risk aversion.\n\n---\n\n**Filename:** `Citigroup_Strategic_Scenario_Evaluation.json`'
# filehandler = FileHandler()
# inline_json = filehandler.extract_json_from_response_text(output)
#
# print(f"inline_json = ",inline_json)