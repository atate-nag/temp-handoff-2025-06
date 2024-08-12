def run_strategy_chains(companyName, problemsFile):
    companyName = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(companyName, problemsFile)

    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        companyName, problemsFile
    )

    with open(trends_file_path, "r") as file:
        trends_data = json.load(file)
    with open(company_file_path, "r") as file:
        company_data = json.load(file)

    print("starting scenario chain")
    print(
        [
            len(x)
            for x in [
                dict_to_plain_text(problem_data),
                dict_to_plain_text(trends_data),
                dict_to_plain_text(company_data),
            ]
        ]
    )

    output_scenario = invoke(
        chain_scenario,
        {
            "problem_statement": dict_to_plain_text(problem_data),
            "trend_document": dict_to_plain_text(trends_data),
            "company_data": dict_to_plain_text(company_data),
            "company_name": "Tesla",
        },
    )

    print("starting framework chain")

    output_framework = invoke(
        chain_framework,
        {
            "problem_statement": dict_to_plain_text(problem_data),
            "trend_document": dict_to_plain_text(trends_data),
            "company_data": dict_to_plain_text(company_data),
            "company_name": "Tesla",
        },
    )
    with open("Intermediates/scenario_output.json", "w") as file:
        json.dump(output_scenario, file, indent=4)

    with open("Intermediates/framework_output.json", "w") as file:
        json.dump(output_framework, file, indent=4)

    print("starting report chain")
    print(
        [
            len(x)
            for x in [
                dict_to_plain_text(company_data),
                dict_to_plain_text(output_scenario),
                dict_to_plain_text(output_framework),
                dict_to_plain_text(trends_data),
            ]
        ]
    )
    output_report = invoke(
        chain_report,
        {
            "company_data": dict_to_plain_text(company_data),
            "scenario_analysis": dict_to_plain_text(output_scenario),
            "framework_analysis": dict_to_plain_text(output_framework),
            "trends": dict_to_plain_text(trends_data),
        },
    )

    print(output_report)
    # Define the output file path
    output_file = f"Strategic Reports/report_{companyName}.txt"

    # Write the report to the output file
    with open(output_file, "w") as file:
        file.write(output_report)


def run_strategy_report_agent(companyName, problemsFile):
    rp_ag = ReportAgent("reporter")
    rp_ag.set_tools([])
    rp_ag.build()
    companyName = companyName.replace(" ", "_").replace(".", "").replace("'", "")
    problem_data = get_problem(companyName, problemsFile)

    # Get the files and paths for the necessary files related to the company and problem
    problem_file_path, trends_file_path, company_file_path = get_file_paths(
        companyName, problemsFile
    )

    with open(trends_file_path, "r") as file:
        trends_data = json.load(file)
    with open(company_file_path, "r") as file:
        company_data = json.load(file)

    # summary_company = summary_chain.invoke(
    #     {
    #         "company": companyName,
    #         "problem_statement": problem_data,
    #         "data": dict_to_plain_text(company_data),
    #     }
    # )
    summary_company = invoke(
        summary_chain,
        {
            "company": companyName,
            "problem_statement": problem_data,
            "data": dict_to_plain_text(company_data),
        },
    )
    summary_trends = invoke(
        summary_chain,
        {
            "company": companyName,
            "problem_statement": problem_data,
            "data": dict_to_plain_text(trends_data),
        },
    )

    # with open("company_summary.txt", "r") as file:
    #     summary_company = file.read()
    # with open("trends_summary.txt", "r") as file:
    #     summary_trends = file.read()

    # Write summaries to text files
    with open(f"Intermediates/{companyName}_company_summary.txt", "w") as file:
        file.write(summary_company)
    with open(f"Intermediates/{companyName}_trends_summary.txt", "w") as file:
        file.write(summary_trends)

    data_summary = (
        "Company data summary: "
        + summary_company
        + "\n"
        + "Trends data summary: "
        + summary_trends
    )
    print(
        {
            "data_summary": data_summary,
            "problem_statement": problem_data,
            "company": companyName,
        }
    )
    plan_data = {
        "data_summary": data_summary,
        "problem_statement": problem_data,
        "company": companyName,
    }
    # plan = evaluate_capability_cluster.invoke(plan_data)
    # print(plan)
    # plan = generate_report_plan.invoke(plan_data)
    plan = invoke(generate_report_plan, plan_data)
    print(json.dumps(plan, indent=4))
    with open("plan.json", "w") as file:
        file.write(json.dumps(plan, indent=4))
    report = plan.copy()
    print(plan)
    for title, content in get_subsections(plan["plan"], "content_statement"):
        data_input = f"""
company data:
{company_data}

Trends:
{trends_data}
"""

        output = invoke(
            rp_ag.writing_chain,
            {
                "report_structure": dict_to_plain_text(plan),
                "data_input": data_input,
                "content_section": title + ": " + content + "\n\n" + problem_data,
            },
        )
        print("************")
        # print(output)
        print(output.keys())
        print(len(output["content"]))
        print(len(output["content_summary"]))
        print("************")
        print(title + ": " + content)
        # contentSection.model_validate(output)
        print("************")
        print("\n\n\n")
        # print(report)
        print("\n\n\n")
        find_and_fill(
            report,
            title,
            output["title"],
            output["content"],
            output["data_needed"],
            output["content_statements"],
        )
        # print(report)
        # assert 1 ==2
    with open(f"Strategic Reports/report_{companyName}.json", "w") as file:
        json.dump(report, file)

    print(report)
    markdown = report_to_markdown(report["plan"], "")

    with open(
        f"Strategic Reports/report_{companyName}_technical_assessment.md", "w"
    ) as file:
        file.write(markdown)
