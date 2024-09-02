from typing import Callable, List, Dict, TypedDict
from typing_extensions import Self
from decomp_task.base import BaseTask, BaseTaskManager, BaseAgents
from pylatex import Command, Document, Section, Subsection, Subsubsection
from pylatex.utils import NoEscape, italic, escape_latex
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from decomp_task.writing.graph import TaskGraph
import uuid

WorkFlowDict = TypedDict(
    "WorkFlowDict", {"prefix": List[int], "string": str, "num": int}
)


class WritingTask(BaseTask):
    def __init__(
        self: Self,
        name: str,
        description: str,
        objectives: list,
        constraints: list,
        root_task: Self,
        id_str: str = None,
        previous_task: Self = None,
        parent_task: Self = None,
        predict: bool = True,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            objectives=objectives,
            constraints=constraints,
            root_task=root_task,
            id_str=id_str,
        )
        self.root_task: Self = self.root_task
        self.previous_task = previous_task
        self.parent_task = parent_task
        self.predict = predict
        self.next_task = None
        self.child_task = None
        self._test_previous_parent()

    @property
    def id(self):
        if self.id_str:
            name = self.id_str
        else:
            name = self.name + str(
                self.parent_task.id if self.parent_task else self.previous_task.id
            )
        return uuid.uuid5(uuid.NAMESPACE_OID, str(type(self)) + name)

    def task_details_str(self: Self, indent=0) -> str:
        constraints_str = "\n".join(
            ["        " + constraint for constraint in self.constraints]
        )
        indent = "    " * indent
        message = (
            f"{indent}Section Title: '{self.name}'\n"
            + f"{indent}Section Description: '{self.description}'\n"
        )
        if self.predict:
            message = (
                f"{message}\n{indent}Section Content Constraints:\n{constraints_str}"
            )
        elif self.execution_output is not None:
            message = f"{message}\n{indent}Section Content:\n{self.execution_output}"

        return message

    def _test_previous_parent(self: Self) -> None:
        if self.previous_task is not None and self.parent_task is not None:
            raise Exception("Cannot have both previous and parent")

    def _get_subsequent_tasks(self: Self) -> List[Self]:
        output = [self]
        while output[-1].next_task is not None:
            output.append(output[-1].next_task)
        return output

    def _get_previous_tasks(self: Self) -> List[Self]:
        output = [self]
        while output[-1].previous_task is not None:
            output.append(output[-1].previous_task)
        return output[::-1]

    def _get_child_tasks(self: Self) -> List[Self]:
        if self.child_task:
            return self.child_task._get_subsequent_tasks()
        else:
            return []

    def _get_leaves(self: Self) -> List[Self]:
        visit = self._get_subsequent_tasks()
        leaf = []
        while len(visit):
            current = visit.pop(0)
            if current.child_task is None:
                leaf.append(current)
            else:
                visit = visit + current.child_task._get_subsequent_tasks()
        return leaf

    def _get_workflow(
        self: Self,
        fns: Callable = None,
        num: int = 1,
        output: List[WorkFlowDict | None] = [],
        prefix: List[int | None] = [],
    ) -> List[WorkFlowDict]:
        inter = {
            "prefix": prefix,
            "string": fns(self) if fns else self._to_string(),
            "num": num,
        }
        output.append(inter)
        if self.child_task is not None:
            output = self.child_task._get_workflow(
                fns=fns, num=1, output=output, prefix=prefix + [num]
            )

        if self.next_task is not None:
            output = self.next_task._get_workflow(
                fns=fns, num=num + 1, output=output, prefix=prefix
            )

        return output

    def workflow(
        self: Self, fns: Callable = None, as_string: bool = True
    ) -> List[WorkFlowDict] | str:
        current_workflow = self._get_workflow(fns=fns, output=[])

        # assert type(current_workflow) == list

        if as_string:
            for i, task_str in enumerate(current_workflow):
                num = task_str["prefix"] + [task_str["num"]]
                current_workflow[i] = (
                    "    " * (len(num) - 1)
                    + ".".join([f"{n}" for n in num])
                    + ") "
                    + task_str["string"]
                )
            current_workflow = "\n".join(current_workflow)
        return current_workflow

    def create_task(self, overriding_args: dict, parent_or_previous: bool) -> Self:
        task_class = type(self)
        parent_task, previous_task = (
            (self, None) if parent_or_previous else (None, self)
        )

        inter = task_class(
            name=overriding_args["name"],
            description=overriding_args.get("description", self.description),
            objectives=overriding_args.get("objectives", self.objectives),
            constraints=overriding_args.get("constraints", self.constraints),
            root_task=self.root_task if self.root_task else self,
            parent_task=parent_task,
            previous_task=previous_task,
            predict=overriding_args.get("predict", self.predict),
        )
        if parent_task:
            self.child_task = inter
        else:
            self.next_task = inter

        return inter


class ConstrainedWritingTask(WritingTask):
    def __init__(self: Self, section_type: str, **other_args: Dict) -> None:
        super().__init__(**other_args)
        self.section_type = section_type
        self.root_task: Self = self.root_task

    def task_details_str(self: Self, indent: int = 0) -> str:
        indent = "    " * indent
        constraints_str = "\n".join(
            [indent + "    " + constraint for constraint in self.constraints]
        )
        message = (
            f"{indent}Section Title: '{self.name}'\n"
            + f"{indent}Section Type: '{self.section_type}'\n"
            + f"{indent}Section Description: '{self.description}'\n"
        )
        if self.predict:
            message = (
                f"{message}\n{indent}Section Content Constraints:\n{constraints_str}"
            )
        elif self.execution_output is not None:
            message = f"{message}\n{indent}Section Content:\n{self.execution_output}"

        return message

    def create_task(self, overriding_args: dict, parent_or_previous: bool) -> Self:
        task_class = type(self)
        parent_task, previous_task = (
            (self, None) if parent_or_previous else (None, self)
        )

        inter = task_class(
            name=overriding_args["name"],
            description=overriding_args.get("description", self.description),
            objectives=overriding_args.get("objectives", self.objectives),
            constraints=overriding_args.get("constraints", self.constraints),
            root_task=self.root_task if self.root_task else self,
            parent_task=parent_task,
            previous_task=previous_task,
            predict=overriding_args.get("predict", self.predict),
            section_type=overriding_args.get("section_type", self.section_type),
        )
        if parent_task:
            self.child_task = inter
        else:
            self.next_task = inter

        return inter


class WritingTaskManager(BaseTaskManager):
    def __init__(
        self: Self,
        root_task: WritingTask | ConstrainedWritingTask,
        task_decomposer,
        condition,
        executer,
        threshold: int = 2,
        max_workers: int = 4,
        **other_args,
    ):
        super().__init__(
            root_task,
            task_decomposer,
            condition,
            executer,
            threshold=threshold,
            **other_args,
        )
        self.max_workers = max_workers

    def get_predicted_plan(self, fns):
        assert self.root_task.predict
        tasks = [[self.root_task]]

        while len(tasks) <= self.threshold:
            current_tasks = tasks[-1]
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                jobs = []
                for current_task in current_tasks:
                    jobs.append(
                        executor.submit(
                            lambda x: x.decompose(self.task_decomposer, self.condition),
                            *(current_task,),
                        )
                    )

                for job in futures.as_completed(jobs):
                    result_done = job.result()

            next_tasks = []
            for current_task in current_tasks:
                if current_task.child_task is not None:
                    next_tasks = (
                        next_tasks + current_task.child_task._get_subsequent_tasks()
                    )

            tasks.append(next_tasks)

        return self.root_task.workflow(fns=fns, as_string=True)

    def dump_to_neo4j(self, task_graph: TaskGraph, keys: List):
        unvisited: List[WritingTask] = [self.root_task]

        while len(unvisited):
            current_task = unvisited.pop(0)
            task_graph.add_task(current_task, keys)
            if current_task is not self.root_task:
                if current_task.parent_task:
                    assert current_task.parent_task.child_task is current_task
                    task_graph.link_child_tasks(current_task.parent_task, current_task)
                elif current_task.previous_task:
                    assert current_task.previous_task.next_task is current_task
                    task_graph.link_sibling_tasks(
                        current_task.previous_task, current_task
                    )
                else:
                    raise Exception("No parent/sibling but not root")

            if current_task.child_task:
                unvisited = unvisited + current_task._get_child_tasks()

    def execute_tasks(self):
        leaves = self.root_task._get_leaves()

        for leaf in leaves:
            leaf.execute(self.executer)

        # report_list = self.root_task.workflow( lambda task : (task.name, (task.execution_output if len(task.execution_output, ) > 0 else ''), task ) , as_string=False)
        # report_list_name = [  r["string"][0] for r in report_list ]
        # for leaf in leaves:
        #     index = report_list_name.index(leaf.name)
        #     if index > 0:
        #         previous_report = list_to_report(report_list[1:index])

        #         system_prompt = "Re-write the section [section to be rewritten] to ensure that the section is cohesive with the current report. "+ \
        #                         "The [section to be rewritten] should not have duplicate phrases or sentence with the current report. " + \
        #                         "Do not change the title. Do not change the format of the section. " + \
        #                         f"Here is the current report\n\n{previous_report}"

        #         num = report_list[index]["prefix"] + [ report_list[index]["num"] ]
        #         num = ".".join([f"{n}" for n in num])
        #         message = f"Section to be rewritten\n{ num + ') ' + leaf.name }\n{leaf.execution_output}"

        #         enhance_section = BaseAgents(
        #             llm_config= self.task_decomposer.setup_config["llm_config"],
        #             silent= self.task_decomposer.setup_config["silent"],
        #             is_termination_msg=self.task_decomposer.setup_config["is_termination_msg"],
        #             user_system_prompt=system_prompt
        #         ).single_with_structure(message)
        #         if leaf.name in enhance_section:
        #             enhance_section = enhance_section[enhance_section.find(leaf.name)+len(leaf.name):].strip()
        #         leaf.execution_output = enhance_section

    def create_document(self, file_name):
        geometry_options = {"margin": "1.54cm"}
        doc = Document(
            f"{file_name}_report", page_numbers=True, geometry_options=geometry_options
        )
        doc.append(NoEscape(r"\tableofcontents"))
        self._fill_document(doc, self.root_task)
        doc.generate_pdf(clean_tex=False)

    def _fill_document(self, doc: Document, task: WritingTask | ConstrainedWritingTask):
        main_sections = task.child_task._get_subsequent_tasks()
        all_cites = []
        for main_section in main_sections:
            with doc.create(Section(main_section.name)):
                if main_section.child_task is not None:
                    sub_sections = main_section.child_task._get_subsequent_tasks()
                    for sub_section in sub_sections:
                        with doc.create(Subsection(sub_section.name)):
                            doc.append(sub_section.execution_output[0])
                            all_cites = all_cites + sub_section.execution_output[1]
                else:
                    doc.append(main_section.execution_output[0])
                    all_cites = all_cites + main_section.execution_output[1]
        all_cites = list(set(all_cites))
        all_cites = [
            f"[{num}] - Source: {self.executer.company_extractor.raw_insights[num][3]}"
            for num in all_cites
        ]
        with doc.create(Section("Appendix")):
            doc.append("\n".join(all_cites))
        return doc


def list_to_report(current_workflow):
    indent = "    "
    for i, task_str in enumerate(current_workflow):
        num = task_str["prefix"] + [task_str["num"]]
        current_workflow[i] = (
            indent * (len(num) - 1)
            + ".".join([f"{n}" for n in num])
            + ") "
            + task_str["string"][0]
            + "\n\n"
            + "\n".join(
                [
                    indent * (len(num) - 1) + r
                    for r in task_str["string"][1].splitlines()
                ]
            )
        )
    current_workflow = "\n".join(current_workflow)
    return current_workflow


if __name__ == "__main__":
    pass
