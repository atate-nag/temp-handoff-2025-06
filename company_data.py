import json
from filehandler import FileHandler

from graph_workflow.full_graph import (
    dump_company_graph_to_plain_txt,
    dump_company_graph_to_json,
    get_trends_from_gics_code,
    save_curated_trend_data,
    get_curated_trend_data,
    save_condensed_trend_data,
    get_condensed_trend_data,
    save_condensed_company_data,
    get_condensed_company_data,
)
from utility import (
    dict_to_plain_text,
    json_to_markdown,
    dict_to_markdown,
    retry,
    condense,
    invoke,
    report_to_markdown,
)

import logging
import logging.config
from config.conf import read_config, setup_config

logger = logging.getLogger("company_data")
logger.info("Started Company Data")
def condense_company_data(company_name, problem):
    # problem = get_problem(company_name, problemsFile)
    logger.info("company_name", company_name)
    logger.info("problem", problem)
    company_data = dump_company_graph_to_json(company_name, problem)

    # the full capabilities
    logger.info("company_data", company_data)
    context = problem
    subject = f"""
The insights and capabilities of {company_name}
    """
    company_data_full = [x for x in company_data["insights"]]
    company_data_full.extend([x for x in company_data["capabilities"]])
    condensed_company_data = condense(
        company_data_full,
        "statement",
        context,
        subject,
        number_of_clusters=50,
        number_of_processes=5,
    )
    logger.info("Saving condensed company data")
    save_condensed_company_data(company_name, problem, condensed_company_data)

company_to_gics = {
    "Tesla": [25],
    "McKesson": [35],
    "Elevance_Health": [35],
    "Costco_Wholesale": [30],
    "Marathon_Petroleum": [10],
    "Exxon_Mobil": [10],
    "Valero_Energy": [10],
    "Chevron": [10],
    "Alphabet": [50],
    "CVS_Health": [35],
    "Walmart": [30],
    "Cardinal_Health": [35],
    "Berkshire_Hathaway": [40],
    "JPMorgan_Chase": [40],
    "AmerisourceBergen": [35],
    "ConocoPhillips": [10],
    "AT&T": [50],
    "Amazon": [25],
    "Kroger": [30],
    "UnitedHealth_Group": [35],
    "Apple": [45],
    "Phillips_66": [10],
    "Ford Motor": [25],
    "Home Depot": [25],
    "General Motors": [25],
    "Centene": [35],
    "Verizon Communications": [35],
    "Walgreens Boots Alliance": [30],
    "Fannie Mae": [40],
    "Comcast": [50],
    "Meta Platforms": [50],
    "Bank of America": [40],
    "Target": [30],
    "Dell Technologies": [45],
    "Archer Daniels Midland": [30],
    "Citigroup": [40],
    "United Parcel Service": [20],
    "Pfizer": [35],
    "Lowe's": [20],
    "Johnson & Johnson": [35],
    "FedEx": [20],
    "Humana": [35],
    "Energy Transfer": [10],
    "State Farm Insurance": [40],
    "Freddie Mac": [40],
    "PepsiCo": [30],
    "Wells Fargo": [40],
    "Walt Disney": [50],
    "Procter & Gamble": [30],
    "General Electric": [20],
    "Albertsons": [30],
    "MetLife": [40],
    "Goldman Sachs Group": [40],
    "Sysco": [30],
    "Raytheon Technologies": [20],
    "Boeing": [20],
    "StoneX Group": [40],
    "Lockheed Martin": [20],
    "Morgan Stanley": [40],
    "Intel": [45],
    "HP": [45],
    "nag": [45],
    "TD Synnex": [45],
    "International Business Machines": [45],
    "HCA Healthcare": [35],
    "Prudential Financial": [40],
    "Caterpillar": [20],
    "Merck": [35],
    "World Fuel Services": [10],
}
gics_mapping = {
    10: "Energy",
    15: "Materials",
    20: "Industrials",
    25: "Consumer Discretionary",
    30: "Consumer Staples",
    35: "Health Care",
    40: "Financials",
    45: "Information Technology",
    50: "Communication Services",
    55: "Utilities",
    60: "Real Estate",
}

def get_problem(company_name: str, problems_file: str) -> str:
    with open(problems_file) as f:
        all_probs = json.load(f)
    key = company_name.replace(" ","_").replace("'","")
    stmt = all_probs.get(key)
    if stmt is None: raise KeyError(f"No problem statement for {company_name}")
    return stmt

def get_gics_code_and_name(company_name: str):
    key = company_name.replace(" ","_").replace("'","")
    codes = company_to_gics.get(key)
    if not codes: raise KeyError(f"No GICS mapping for {company_name}")
    return codes, [gics_mapping.get(c,"Unknown") for c in codes]

def condense_trends(company_name, problemsFile):
    gics_code, _ = get_gics_code_and_name(company_name)
    trends = get_curated_trend_data(company_name, gics_code, problemsFile)
    problem = get_problem(company_name, problemsFile)
    context = problem
    subject = f"""
The trends impacting {company_name}
    """
    if not trends:
        trends = get_trends_from_gics_code(gics_code, problem)
        trends = trends["trends"]
        save_curated_trend_data(company_name, gics_code, problem, trends)
    condensed_trends = condense(
        trends,
        "statement",
        context,
        subject,
        number_of_clusters=10,
        number_of_processes=5,
    )

    save_condensed_trend_data(company_name, problem, condensed_trends)



def get_trends(company_name, problemFile, force_recreate=False):
    """
    Retrieves the trends for a given company.
    Will load from archive if available, otherwise will generate new trends unless force_recreate is set to True.
    Will store to archive after generation.
    """
    problem = get_problem(company_name, problemFile)
    gics_code, gics_name = get_gics_code_and_name(company_name)
    logger.debug(f"gics_code: {gics_code}")
    condense_trend_data = get_condensed_trend_data(company_name, problem)
    curated_trend_data = get_curated_trend_data(company_name, gics_code, problem)

    trend_data = None  # Initialize trend_data

    if condense_trend_data and not force_recreate:
        logger.debug(f"Loaded condensed trends from archive")
        trend_data = condense_trend_data
    elif curated_trend_data and not force_recreate:
        logger.debug(f"Loaded trends from archive")
        trend_data = condense_trends(company_name, problemFile)
    else:
        curated_trend_data = get_trends_from_gics_code(gics_code, problem)
        logger.debug(f"Generated trends")
        save_curated_trend_data(company_name, gics_code, problem, curated_trend_data)
        trend_data = condense_trends(company_name, problemFile)
        logger.debug(f"Saved trends to archive")

    # implement validation and checking of trends

    return trend_data

def get_company_data(companyName, problem_statement):
    """
    Retrieves the full data for a given company
    """
    condensed_company_data = get_condensed_company_data(companyName, problem_statement)
    if condensed_company_data:
        company_full_data = condensed_company_data
    else:
        condense_company_data(companyName, problem_statement)
        company_full_data = get_condensed_company_data(companyName, problem_statement)
    # implement validation and checking of trends
    return company_full_data


def get_file_paths(company_name, problemsFile, file_handler):
    """
    Give a single company, extracts the problem, company and trend data
    and generates files suitable for agent processing
    """
    conf = read_config()
    run_id = "_" + conf.get("run_id")

    company_name = company_name.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(company_name, problemsFile)
    problem_file_path = file_handler.write_local_json(
        f"problem_{company_name}" + run_id, json.dumps(problem_data)
    )
    trends = get_trends(company_name, problemsFile, force_recreate=False)
    company_full_data = get_company_data(company_name, problem_data)

    trends_file_path = file_handler.write_local_json(
        f"company_trends_{company_name}" + run_id, json.dumps(trends)
    )

    company_file_path = file_handler.write_local_json(
        f"company_data_{company_name}" + run_id, json.dumps(company_full_data)
    )
    return problem_file_path, trends_file_path, company_file_path

# --- BASIC YFINANCE FETCH ----------------------------------------------------
import yfinance as yf

ticker_map = {"Citigroup": "C",  # add others as needed
              "Apple": "AAPL",
              "Tesla": "TSLA"}


import yfinance as yf

def fetch_basic_financials(ticker: str) -> dict:
    """Lightweight pull to avoid rate-limits."""
    tkr   = yf.Ticker(ticker)
    fin   = tkr.fast_info   # uses cached endpoint
    bal   = tkr.balance_sheet
    roe   = None
    if "Total Stockholder Equity" in bal and "Net Income" in bal:
        equity = bal.loc["Total Stockholder Equity"].iloc[0]
        income = bal.loc["Net Income"].iloc[0]
        roe = None
        if equity:
            roe = round(income / equity * 100, 1)
    return {
        "price":      fin.get("last_price"),
        "mkt_cap":    fin.get("market_cap"),
        "roe_pct":    roe,
        "debt_to_equity": fin.get("total_debt") / fin.get("total_stockholder_equity")
                          if fin.get("total_stockholder_equity") else None,
    }
