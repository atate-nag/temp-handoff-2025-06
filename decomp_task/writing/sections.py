from collections import namedtuple

report = {
    "section": "report",
    "description" : "This is the full report",
    "ordering" : 1,
    "multiple" : False,
    "sub_sections" : 
    [
        {
            "section": "summary",
            "description": "Section that provides the summary of the report, purpose of the report, reiterate main points, etc.",
            "ordering" : 1,
            "multiple" : False,
            "sub_sections": [
                {
                    "section": "executive summary",
                    "description": "executive summary of the report",
                    "ordering" : 1,
                    "multiple" : False,
                },
                {
                    "section": "abstract",
                    "description": "The purpose of the report",
                    "ordering" : 1,
                    "multiple" : False,
                },

            ]
        },
        {
            "section": "main body",
            "ordering" : 2,
            "description": "Section that represents the core body of the report.",
            "sub_sections": [
                {
                    "section": "foundational information",
                    "ordering" : 1,
                    "description": "A short sections that provides information regarding a topic or concept, such as definitions, historical context, etc. to provide foundational context to the report.",
                    "multiple" : False,
                },    
                {
                    "section": "report justification",
                    "ordering" : 2,
                    "description": "A short section that justifies the purpose of the report",
                    "multiple" : False
                },
                {
                    "section": "core information",
                    "ordering" : 3,
                    "description": "Sections that represent a single deep analysis of a topic, subject or concept. This section must not contain strategy recommendation or implementation. Common types of analysis are: Strategy Framework, Competitor, Market, Industry, Customer or Financial.",
                    "multiple" : True,
                    "sub_sections": [                    
                        # {
                        #     "section": "exploration and explanation",
                        #     "ordering" : 1,
                        #     "description": "In depth exploration or description of a subject, topic or issue, that frames or limits the scope of the report.",
                        #     "multiple" : True,
                        # },
                        # {
                        #     "section": "core analysis",
                        #     "ordering" : 1,
                        #     "description": "Sections that represent analysis, which includes, but isn't limited to, Strategy (SWOT, PESTLE), Competitor, Market, Industry, Customer or Financial Analysis.",
                        #     "multiple" : True,                        
                        # }
                    ]
                },
                # {
                #     "section": "derived information",
                #     "ordering" : 3,
                #     "description": "Sections that presents derived information such insights, future projections and opinions based on core information sections. These derived information will be foundational for strategy recommendation",
                #     "multiple" : True,
                #     # "sub_sections": [                    
                #     #     {
                #     #         "section": "future outlook",
                #     #         "ordering" : 1,
                #     #         "description": "Section that provides future outlook or trends derived from core information sections, alongside assumptions.",
                #     #         "multiple" : True,
                            
                #     #     },
                #     #     {
                #     #         "section": "opinion",
                #     #         "ordering" : 1,
                #     #         "description": "Provides the writers' opinion a subject or topic identified in core information sections.",
                #     #         "multiple" : True,
                            
                #     #     },
                #     #     {
                #     #         "section": "insights",
                #     #         "ordering" : 1,
                #     #         "description": "Provides derived insights based on the analysis in the core information.",
                #     #         "multiple" : True,                          
                #     #     }
                #     # ]
                # },
                {
                    "section": "strategy recommendation",
                    "ordering" : 4,
                    "multiple" : True,
                    "description": "A sections that provides strategy recommendations and accompanying justification or scenario planning. The recommendation must be based on previous section's analysis. This section should not contain implementation details.",
                    "sub_sections": [
                        {
                            "section": "detail recommendation",
                            "ordering" : 1,
                            "multiple" : False,
                            "description": "Section that details of recommendation that address the strategy problem",                        
                        },
                        {
                            "section": "scenario analysis",
                            "ordering" : 2,
                            "multiple" : False,
                            "description": "Section that provides justifies recommendation through scenario analysis.",
                        },
                        {
                            "section": "risk analysis and management",
                            "ordering" : 3,
                            "multiple" : False,
                            "description": "Identification of potential risks of the strategy and how to mitigate them."
                        }
                    ]
                },                 
                # {
                #     "section": "strategy implementation plan",
                #     "ordering" : 5,
                #     "description": "A section describing implementation details of the recommended strategies, including timelines, resource allocation, and milestones.",
                #     "sub_sections": [
                #         {
                #             "section": "action steps",
                #             "ordering" : 1,
                #             "multiple" : False,
                #             "description": "Specific steps required to execute the implementation plan."
                #         },
                #         {
                #             "section": "resource allocation",
                #             "ordering" : 2,
                #             "multiple" : False,
                #             "description": "Details for all resources (financial, human, technological) needed to implement the strategy."
                #         },
                #         {
                #             "section": "timeline and milestones",
                #             "ordering" : 3,
                #             "multiple" : False,
                #             "description": "Detailed timeline for the implementation of the strategy, including key milestones and deadlines."
                #         },
                #         {
                #             "section": "performance measurement",
                #             "ordering" : 4,
                #             "multiple" : False,
                #             "description": "Mechanisms for measuring the success of the implemented strategy, including Key Performance Indicators (KPIs) and other metrics.",
                #             "sub_sections": [
                #                 {
                #                     "section": "key performance indicators (KPIs)",
                #                     "ordering" : 1,
                #                     "multiple" : False,
                #                     "description": "Specific metrics to track the performance of the implemented strategy."
                #                 },
                #                 {
                #                     "section": "monitoring and evaluation",
                #                     "ordering" : 1,
                #                     "multiple" : False,
                #                     "description": "Processes for continuous monitoring and periodic evaluation of strategy implementation."
                #                 }
                #             ]
                #         }                    
                #     ]
                # },                       
            ]
        },
        # {
        #     "section": "appendices",
        #     "ordering" : 3,
        #     "multiple" : False,
        #     "description": "Supporting documents, data, and supplementary information that provide additional context or evidence for the report.",
        #     "sub_sections": []
        # }
    ]
}



SectionType = namedtuple('SectionType', 'name description sub_sections ordering multiple')
free_form = SectionType("standard", "Represents a standard section of a report.", [], 1 , True)
def create_named_tuple(section, final_output={}):    
    if "sub_sections" not in section:
        sub_section_tuple = []
    elif len(section["sub_sections"]) == 0 :
        sub_section_tuple = [ free_form ]        
    else:
        sub_section_tuple = []
        for sec in section["sub_sections"]:
            sub, final_output = create_named_tuple( sec, final_output )
            sub_section_tuple.append(sub)        
    
    st = SectionType( section["section"], section["description"], sub_section_tuple, section["ordering"] , section.get("multiple", False) )
    final_output[st.name] = st
    return st, final_output


_, section_dict = create_named_tuple(report)
section_dict[free_form.name] = free_form

def get_available_section_selector(parent_section_type:str, last_created_section_type:str = None, return_raw:bool = False, single:bool = False)->str:

    if parent_section_type not in section_dict:
        return f"Not a valid parent section name. Valid section names are : {list(section_dict)}"
    
    section = section_dict[parent_section_type]

    if len(section.sub_sections) == 0:
        return "Parent section has no sub-section available."

    ordering = 1 
    if last_created_section_type is not None:
        last_sub_section = section_dict[last_created_section_type]        
        ordering = last_sub_section.ordering + (1 if not last_sub_section.multiple else 0)
            
    sub_sections = [ sub for sub in  section.sub_sections if sub.ordering >= ordering ]

    if return_raw:
        return sub_sections

    if len(sub_sections):
        sub_sections = sections_to_str(sub_sections, single)        
        return "Available Section Types:\n\n" + "\n\n".join(sub_sections)
    else:
        return ""

def sections_to_str(sections, single):
    output = [""]*len(sections)
    for i,sub in enumerate(sections):    
        sub_str =   f'Name: {sub.name}\n' + \
                    f'Description: {sub.description}.'
        if single:
            sub_str = f'{sub_str}\nMultiple:{ "There can multiple sub-section of this type" if sub.multiple else "There can only be sub-section of this type" }'
        output[i] = sub_str
    
    return output


if __name__ == "__main__":
    print(section_dict)
