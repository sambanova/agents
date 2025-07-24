from typing import List
from pydantic import BaseModel, Field

class AtomicTask(BaseModel):
    atomic_task : str = Field(description="The atomic task that needs to be done to implement the step, meaning a single diff edit in the file it self that should be executed")
    additional_context: str = Field("", description="Extract from the research any additional context that can be useful to know to complete this task")

class ImplementationTask(BaseModel):
    file_path : str  = Field(description="The file path to be affected by the implementation step")
    logical_task: str = Field(description="The description of the logical task of what we want to achieve by editing or creating the file")
    atomic_tasks : List[AtomicTask] = Field(description="The atomic tasks that need to be done to implement the step")

class ImplementationPlan(BaseModel):
    tasks: List[ImplementationTask] = Field( description="The list of tasks that need to be done to implement the plan")
