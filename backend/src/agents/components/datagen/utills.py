import re


def drop_think_section(text_string):
  """
  Removes the <think>...</think> section from a given string.

  Args:
    text_string: The input string that may contain <think> tags.

  Returns:
    The string with the <think> section removed.
  """
  # The regex pattern looks for:
  # <think> - literal <think> tag
  # .*?     - any character (.), zero or more times (*), non-greedily (?)
  # </think> - literal </think> tag
  # re.DOTALL makes '.' match newlines as well, so it works across multiple lines.
  pattern = r"<think>.*?</think>"
  cleaned_string = re.sub(pattern, "", text_string, flags=re.DOTALL)
  return cleaned_string