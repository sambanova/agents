import os
import re
import sys
import time
import openai

def get_prompt_score(question: str, answer: str):
    # Inspired by Figure 6 of https://arxiv.org/abs/2411.15594

    return f"""Given the following question and answer, rate the answer between 1 and 5 (integer score, higher is better)?
    Question: {question}
    Answer: {answer}"""

def get_prompt_preference(question: str, answer0: str, answer1: str):
    # Inspired by Figure 6 of https://arxiv.org/abs/2411.15594

    return f"""Given the following question, which answer is better? Answer "Answer 0" or "Answer 1".
    You do not need to explain the reason.
    Question: {question}
    Answer 0: {answer0}
    Answer 1: {answer1}"""

def get_messages(prompt: str):
    return [
        { "role" : "system", "content" : "You are a helpful assistant" },
        { "role" : "user", "content": prompt }
    ]

def get_judge_score(model: str, question: str, answer: str) -> int:
    prompt = get_prompt_score(question, answer)
    messages = get_messages(prompt)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )

    result = response.choices[0].message.content

    print(result)

    # TODO: sometimes the answer is "I would rate this answer a 5 out of 5. Here's why:" so extracting the last integer is not sufficient.

    try:
        # Extract last integer from the response.
        return int(re.search("(\d+)(?!.*\d)", result).group(0))
    except AttributeError:
        return -1

def get_judge_preference(model: str, question: str, answer0: str, answer1: str) -> str:
    prompt = get_prompt_preference(question, answer0, answer1)
    messages = get_messages(prompt)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )

    result = response.choices[0].message.content

    print(result)

    is_answer_0 = re.search("[Aa]nswer 0", result)
    is_answer_1 = re.search("[Aa]nswer 1", result)

    if is_answer_0 and is_answer_1:
        return "TIE"
    elif is_answer_0:
        return "0"
    elif is_answer_1:
        return "1"
    else:
        return "UNKNOWN"

def sort_by_suffix(l):
    return sorted(l, key=lambda x: x.split("_")[1])

def count_words(s):
    return len(re.findall(r"\b\w+\b", s))

def main(client, data_dir, use_azure):
    data = { "name": [], "question": [], "answer": [], "reference": [] }

    for filename in sort_by_suffix(os.listdir(data_dir)):
        # print(filename)

        q_or_a, name = filename.removesuffix(".txt").split("_")

        if name not in data["name"]:
            data["name"].append(name)

        with open(os.path.join(data_dir, filename), "r") as f:
            data[q_or_a].append(f.read())

    # print(data)

    if use_azure:
        model = "gpt-4o"
    else:
        model = "Meta-Llama-3.3-70B-Instruct"

    print(f"Judge model: {model}")

    for name, question, answer, reference in zip(data["name"], data["question"], data["answer"], data["reference"]):
        print("---------------------------------------------------")
        print(name, question, count_words(answer), count_words(reference))

        preference = "MISSING"
        answer_score = -2
        reference_score = -2

        reference = postprocess_text(reference)

        if answer != "" and reference != "":
            preference = get_judge_preference(model, question, answer, reference)

        if answer != "":
            answer_score = get_judge_score(model, question, answer)

        if reference != "":
            reference_score = get_judge_score(model, question, reference)

        print(f"PREFERENCE: {preference}")
        print(f"ANSWER_SCORE: {answer_score}")
        print(f"REFERENCE_SCORE: {reference_score}")

def postprocess_text(text: str) -> str:
    # TODO: Remove numbers before '.' and '\n'. Perplexity does this for sources.
    return text

if __name__ == "__main__":
    use_azure = False

    if use_azure:
        api_key = os.getenv("AZURE_API_KEY")
        azure_endpoint = os.getenv("AZURE_ENDPOINT")
        client = openai.AzureOpenAI(api_key=api_key, api_version="2024-02-15-preview", azure_endpoint=azure_endpoint)
    else:
        api_key = os.getenv("SAMBANOVA_API_KEY")
        client = openai.OpenAI(api_key=api_key, base_url="https://api.sambanova.ai/v1")

    data_dir = "./demo"

    sys.exit(main(client, data_dir, use_azure))
