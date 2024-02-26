# Project Name

This is the end-to-end demonstrator of Socrates for the straegy use-case

## Getting Started

It should not be complex to run, just follow these steps. 

### Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.x
- pip (Python package installer)

### Setting Up Your Development Environment

1. **Clone the Repository**

   Start by cloning the repository to your local machine:

   ```bash
   git clone https://gitlab.com/your-username/your-project-name.git
   cd your-project-name

2. **Create a `.env` File**

   In the root directory of your project, create a file named `.env`:


   Make sure that it contains the line
   OPENAI_API_KEY=your_api_key_here

   Security note: ensure the .env file is added to your .gitignore file to prevent accidentally committing your OpenAI API key to version control.

3. **Create a Virtual Environment**

Next, create a virtual environment in the project directory:

   On macOS and Linux:
   python3 -m venv env
   source env/bin/activate

With the virtual environment activated, install the project dependencies:

pip install -r requirements.txt

4. **Copy your data sources**

There are three directories for data

./Files-DATA/ -> raw data about the company you are interested in
./Files-INSIGHT/ -> Documents that potentially contain insghts about the comapny (e.g. internal docs)
./Files-MARKET/ -> Documents that potentially contain insights about the environment (e.g market reports)

Copy appropriate files in PPT/PPTX, PDF or DOC/DOCX format to those directories. 


4. **Run the application**

python strategy_executor.py


## NOTE:

The the application will currentl run in parallel with the same number of workers as there
are file in the FILES-Insight directory. More flexibility is coming up in this regard. 

The more files you provide, the longer in general the run wil take. 

5. **Check Output**

The tool outputs a strategy presentation called "strategy_presentation.pptx"


