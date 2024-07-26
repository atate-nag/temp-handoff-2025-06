# Project Name

This is the dynamic workflow executor of Socrates for the straegy use-case
This supercedes the strategy_executor.py. This version requies neo4j desktop 
is already installed on your machine.

## Getting Started


### Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.x
- pip (Python package installer)
- neo4j desktop

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
   NEO4J_USER=your_neo4j_user
   NEO4J_PASSWORD=your_neo4j_password

   Security note: ensure the .env file is added to your .gitignore file to prevent accidentally committing your OpenAI API key to version control.

3. **Create a Virtual Environment**

Next, create a virtual environment in the project directory:

   On macOS and Linux:
   python3 -m venv env
   source env/bin/activate

With the virtual environment activated, install the project dependencies:

pip install -r requirements.txt

4. **Copy your data sources**

You have to run the following export to give the TIKA python package access to your local server:

   export TIKA_SERVER_JAR=${PWD}/tika_server/graph_workflow

Files should be added to the following folders:

data/sources/wikipedia
data/sources/perigon
data/sources/reportLinker

The workflow for feeding the data into the graph is:

"fill_graph_Tesla":{
      "function": "fill_graph",
      "parameters": {
        "companies": ["Tesla"]
      },
      "enabled": true
    },


Copy appropriate files in PPT/PPTX, PDF or DOC/DOCX format to those directories. 


5. ** Modify the workflow configuration **

Modify the workflow_config.json file to turn on the selective workflow components. The names are self-explanatory but this
is what is supported so far

### administrative routines

- "cleanUp": clean_up

### graph manipulation and display routines

- "fill_graph": fill_graph, "parameters": {
            "companies": ["Tesla"],
         }
- "getInsights": get_insights, "parameters": {
            "companies": ["Tesla"],
            "delete_existing_insights": true
         }
- "getTrends": generate_trends, "parameters": {
            "folders": ["10. Energy", "25. Consumer Discretionary"],
            "number_of_processes": 5
         }

- getCapabilities: "get_capabilities_tesla" : {
      "step": "getCapabilities",
      "enabled": true,
      "parameters": {
        "companies": ["Tesla"],
        "compute_embeddings" : false,
        "number_of_processes" : 5
      }
    },
- "runStrategy" : {
      "enabled": false,
      "parameters": {
        "companyName": "Tesla",
        "problemsFile" : "./problem_statements.json"
      }
    },
- "runStrategyChain" : {
      "step": "runStrategyChains",
      "enabled": true,
      "parameters": {
        "companyName": "Tesla",
        "problemsFile" : "./problem_statements.json"
      }
    },
- "runFrameworks": run_frameworks,
- "runScenarios": run_scenarios,

   


E.g. setting 

   "evaluateCapabilities": {
      "enabled": true,
      "parameters" : {
        "companyName": "nag",
        "debug" : false,
        "updateGraph" : true
      }


Will enable the evaluation of Capabilities of a company, with Insights that evidence those capabilties. 
This workflow is always going to use the state of the data stored in the knowledge graph. So you should selectively swtich on the elements of the workflow that 
you want to test in isolation. So you will have had to have generated the appropriate parts of the neo4j database in advance or run in debug mmode to use debug files. 

4. **Run the application**

python graph_workflow.py

The more files you provide, the longer in general the run wil take. 

5. **Check Output**
