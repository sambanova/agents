_type: "chat"
- input_variables:
  - task
  - research
  - additional_context
  - file_path

# System
You are a senior skilled developer assistant implement a code change according to concrete task.

# Human

## Rules
1. take into account the research that you already did inorder to implement the task
2. take into account the additional context if exists

## Additional Context
{additional_context}

## Task
{task}

# Human
First conduct the research

# Placeholder
{research}

# Human
Your job is to create a new file {file_path} to implement the task {task} based on the research you conducted.
Write the code now


